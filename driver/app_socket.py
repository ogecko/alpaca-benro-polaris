import asyncio
import json
import logging
import socket
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

import uvicorn
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from config import Config
from polaris import Polaris
from shr import LifecycleController, format_timestamp


# ── Subscription registry ─────────────────────────────────────────────────────
# All access is from the event loop thread only — no locking needed.
subscriptions:   Dict[str, Dict[WebSocket, Dict[str, Any]]] = {}
client_activity: Dict[WebSocket, datetime] = {}
active_clients:  set[WebSocket] = set()


# ── Client lifecycle ──────────────────────────────────────────────────────────

async def socket_handler(websocket: WebSocket):
    await websocket.accept()
    active_clients.add(websocket)
    client_activity[websocket] = datetime.now(timezone.utc)
    logger = logging.getLogger()
    try:
        while True:
            if websocket.client_state != WebSocketState.CONNECTED:
                raise WebSocketDisconnect(1006)
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "ping":
                client_activity[websocket] = datetime.now(timezone.utc)
                await ws_safe_send_json(websocket, {"type": "pong"})
                continue

            if Config.log_alpaca_actions:
                logger.info(f"==WS== Received message: {msg}")

            if msg_type == "subscribe":
                topic = msg.get("topic")
                if topic:
                    client_activity[websocket] = datetime.now(timezone.utc)
                    subscriptions.setdefault(topic, {})[websocket] = msg.get("filter", {})
                    for entry in PublishLogTopic.get_backlog(topic):
                        await ws_safe_send_json(websocket, entry)

            elif msg_type == "unsubscribe":
                topic = msg.get("topic")
                if topic:
                    subscriptions.get(topic, {}).pop(websocket, None)

    except asyncio.CancelledError:
        pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.getLogger().info(f"==EXCEPTION== WebSocket error: {e}")
    finally:
        await _remove_client(websocket)      # always clean up, even on CancelledError


async def _remove_client(ws: WebSocket):
    active_clients.discard(ws)
    client_activity.pop(ws, None)
    for topic_subs in subscriptions.values():
        topic_subs.pop(ws, None)
    if ws.client_state != WebSocketState.DISCONNECTED:
        try:
            await ws.close()
        except Exception:
            pass


async def cleanup_inactive_clients(timeout_seconds: int = 10):
    while True:
        await asyncio.sleep(2)
        now = datetime.now(timezone.utc)
        stale = [
            ws for ws, last_seen in list(client_activity.items())
            if (now - last_seen) > timedelta(seconds=timeout_seconds)
        ]
        for ws in stale:
            if Config.log_alpaca_actions:
                logging.getLogger().info(f"==TIMEOUT== Removing inactive client: {ws}")
            await _remove_client(ws)


# ── Safe send ─────────────────────────────────────────────────────────────────

async def ws_safe_send_json(ws: WebSocket, payload: dict):
    if ws not in active_clients:
        return
    try:
        await asyncio.wait_for(ws.send_json(payload), timeout=1.0)
    except Exception:
        await _remove_client(ws)


# ── Status publisher ──────────────────────────────────────────────────────────

async def publish_status(polaris: Polaris):
    while True:
        await asyncio.sleep(0.2)
        subs = list(subscriptions.get("status", {}).keys())
        if not subs:
            continue
        payload = {"type": "status", "data": polaris.getStatus()}
        await asyncio.gather(
            *[ws_safe_send_json(ws, payload) for ws in subs],
            return_exceptions=True
        )


# ── Log publisher ─────────────────────────────────────────────────────────────

class PublishLogTopic(logging.Handler):
    _buffers:      Dict[str, deque] = {}
    _queues:       Dict[str, asyncio.Queue] = {}
    _sender_tasks: Dict[str, asyncio.Task] = {}
    _maxlen = 150

    def __init__(self, topic: str):
        super().__init__()
        self.topic = topic
        if topic not in self._buffers:
            self._buffers[topic] = deque(maxlen=self._maxlen)

    @classmethod
    def start_senders(cls):
        """Start one sender task per topic. Call once from async context at startup."""
        for topic in list(cls._queues):
            cls._ensure_sender(topic)

    @classmethod
    def _ensure_sender(cls, topic: str):
        task = cls._sender_tasks.get(topic)
        if task is None or task.done():
            cls._sender_tasks[topic] = asyncio.create_task(
                cls._sender_loop(topic), name=f'ws_sender_{topic}'
            )

    @classmethod
    async def _sender_loop(cls, topic: str):
        """Long-lived sender — one per topic. Drains queue and broadcasts."""
        queue = cls._queues[topic]
        while True:
            try:
                payload = await queue.get()
                subs = list(subscriptions.get(topic, {}).keys())
                if subs:
                    await asyncio.gather(
                        *[ws_safe_send_json(ws, payload) for ws in subs],
                        return_exceptions=True
                    )
                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def emit(self, record):
        """Called from logging thread — must be non-blocking and thread-safe."""
        try:
            payload = self.format(record)
            self._buffers[self.topic].append(payload)

            queue = self._queues.get(self.topic)
            if queue is None:
                # First emit before start_senders — create queue and schedule sender
                queue = asyncio.Queue(maxsize=200)
                self._queues[self.topic] = queue
                # Schedule sender creation on the event loop thread safely
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(self._ensure_sender, self.topic)

            if subscriptions.get(self.topic):
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    pass   # drop — UI misses a log line, loop never stalls
        except Exception:
            pass

    @classmethod
    def get_backlog(cls, topic: str) -> list:
        return list(cls._buffers.get(topic, []))


# ── Formatter ─────────────────────────────────────────────────────────────────

class PayloadFormatter(logging.Formatter):
    def __init__(self, topic: str):
        super().__init__()
        self.topic = topic

    def format(self, record: logging.LogRecord) -> dict:
        data = record.msg if isinstance(record.msg, dict) else {"text": record.getMessage()}
        try:
            json.dumps(data)
        except TypeError:
            data = {"text": str(data)}
        return {
            "ts":    format_timestamp(record.created),
            "topic": self.topic,
            "level": record.levelname,
            "data":  data,
        }


def attach_publisher_to_logger(topic: str, level=logging.INFO):
    name   = '' if topic == "log" else topic
    logger  = logging.getLogger(name)
    handler = PublishLogTopic(topic)
    handler.setFormatter(PayloadFormatter(topic))
    if not any(isinstance(h, PublishLogTopic) and h.topic == topic for h in logger.handlers):
        logger.addHandler(handler)
    if name:
        logger.propagate = False
        logger.setLevel('INFO')
    return logger


# ── Server entry point ────────────────────────────────────────────────────────

async def alpaca_socket_httpd(logger, lifecycle: LifecycleController, polaris):
    polaris._cm.logTestData(polaris._cm.test_data.keys())
    socket_server = None
    try:
        PublishLogTopic.start_senders()

        socket_app = Starlette(routes=[WebSocketRoute("/ws", socket_handler)])
        socket_config = uvicorn.Config(
            socket_app,
            host=Config.alpaca_restapi_ip_address,
            port=Config.alpaca_socket_port,
            log_level="error",
            ws_per_message_deflate=False,        # disable permessage-deflate compression
        )
        socket_server = uvicorn.Server(socket_config)
        logger.info(f'==STARTUP== Serving Alpaca Pilot WebSocket on '
                    f'{Config.alpaca_restapi_ip_address}:{Config.alpaca_socket_port}')

        await asyncio.gather(
            lifecycle._wrap(socket_server.serve()),
            lifecycle._wrap(publish_status(polaris)),
            lifecycle._wrap(cleanup_inactive_clients(timeout_seconds=10)),
            lifecycle.wait_for_event()
        )
    except asyncio.CancelledError:
        logger.info("==CANCELLED== Alpaca Pilot WebSocket cancel received.")
    except socket.gaierror:
        raise RuntimeError("WebSocket server failed to start due to invalid host.")
    except Exception as e:
        logger.info(f"==EXCEPTION== Alpaca Pilot WebSocket unhandled exception: {e}")
    finally:
        logger.info("==SHUTDOWN== Alpaca Pilot WebSocket shutting down.")
        if socket_server and socket_server.started:
            socket_server.should_exit = True
            await socket_server.shutdown()