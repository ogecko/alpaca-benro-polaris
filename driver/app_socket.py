import asyncio
import json
import logging
from polaris import Polaris
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from collections import deque
import uvicorn
import socket
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState, WebSocketClose
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute

from config import Config
from shr import LifecycleController, LifecycleEvent

# Subscription registry: topic → { websocket → filter }
subscriptions: Dict[str, Dict[WebSocket, Dict[str, Any]]] = {}
client_activity: Dict[WebSocket, datetime] = {}
active_clients: set[WebSocket] = set()

async def socket_handler(websocket: WebSocket):
    await websocket.accept()
    active_clients.add(websocket)
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

            logger.info(f"==WS== Received message: {msg}")
            if msg_type == "subscribe":
                topic = msg.get("topic")
                filter_args = msg.get("filter", {})
                if topic:
                    subscriptions.setdefault(topic, {})[websocket] = filter_args
                    # Send backlog if available
                    backlog = PublishLogTopic.get_backlog(topic)
                    for entry in backlog:
                        try:
                            await ws_safe_send_json(websocket, entry)
                        except Exception:
                            await _remove_client(websocket)

            elif msg_type == "unsubscribe":
                topic = msg.get("topic")
                if topic and topic in subscriptions:
                    subscriptions[topic].pop(websocket, None)

            elif msg_type == "command":
                # Future: handle restart/reload/etc
                pass
    except asyncio.CancelledError:
        await _remove_client(websocket)
    except WebSocketDisconnect:
        await _remove_client(websocket)
    except Exception as e:
        logging.getLogger().info(f"==EXCEPTION== WebSocket error: {e}")
        await _remove_client(websocket)

async def _remove_client(ws: WebSocket):
    for topic_subs in subscriptions.values():
        topic_subs.pop(ws, None)
    client_activity.pop(ws, None)
    active_clients.discard(ws)
    if ws.client_state == WebSocketState.DISCONNECTED:
        return
    try:
        await ws.close()
    except RuntimeError:
        pass  # already closed

async def cleanup_inactive_clients(timeout_seconds: int = 10):
    while True:
        await asyncio.sleep(2)
        now = datetime.now(timezone.utc)
        stale_clients = [
            ws for ws, last_seen in client_activity.items()
            if (now - last_seen) > timedelta(seconds=timeout_seconds)
        ]
        for ws in stale_clients:
            logging.getLogger().info(f"==TIMEOUT== Removing inactive subscription client: {ws}")
            await _remove_client(ws)

async def ws_safe_send_json(ws: WebSocket, payload: dict):
    if ws in active_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            await _remove_client(ws)

def _matches_filter(payload: Dict[str, Any], filter_args: Dict[str, Any]) -> bool:
    for key, val in filter_args.items():
        if payload.get(key) != val:
            return False
    return True

async def publish_status(polaris: Polaris):
    while True:
        await asyncio.sleep(0.2)
        statusdata = polaris.getStatus()
        payload = {"type": "status", "data": statusdata}
        for ws, filter_args in subscriptions.get("status", {}).copy().items():
            try:
                await ws.send_json(payload)
            except (WebSocketDisconnect, RuntimeError):
                await _remove_client(ws)

class PublishLogTopic(logging.Handler):
    _buffers: Dict[str, deque] = {}
    _maxlen = 100

    def __init__(self, topic: str):
        super().__init__()
        self.topic = topic
        if topic not in self._buffers:
            self._buffers[topic] = deque(maxlen=self._maxlen)

    def emit(self, record):
        try:
            payload = self.format(record)
            self._buffers[self.topic].append(payload)
            for ws, filter_args in subscriptions.get(self.topic, {}).copy().items():
                asyncio.create_task(ws.send_json(payload))
        except Exception:
            pass

    @classmethod
    def get_backlog(cls, topic: str) -> list:
        return list(cls._buffers.get(topic, []))

class PayloadFormatter(logging.Formatter):
    def __init__(self, topic: str):
        super().__init__()
        self.topic = topic
    def format(self, record: logging.LogRecord) -> dict:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        data = record.msg if isinstance(record.msg, dict) else {"text": record.getMessage()}
        try:
            json.dumps(data)  # Validate serializability
        except TypeError:
            data = {"text": str(data)}
        return {
            "ts": ts,
            "topic": self.topic,
            "level": record.levelname,
            "data": data
        }


def attach_publisher_to_logger(topic: str, level=logging.INFO):
    name = '' if topic == "log" else topic  # Root logger for "log" topic
    logger = logging.getLogger(name)        # Create or get existing logger
    handler = PublishLogTopic(topic)        # Create handler for this topic
    handler.setFormatter(PayloadFormatter(topic))
    if not any(isinstance(h, PublishLogTopic) and h.topic == topic for h in logger.handlers):
        logger.addHandler(handler)
    if name:
        logger.propagate = False            # Dont propagate published topics to root logger
        logger.setLevel('INFO')             # Default level for non-root loggers
    return logger

async def alpaca_socket_httpd(logger, lifecycle: LifecycleController, polaris):
    log_logger = attach_publisher_to_logger("log")  # general log
    pid_logger = attach_publisher_to_logger("pid")  # pid controller
    kf_logger = attach_publisher_to_logger("kf")    # kalman filter
    cm_logger = attach_publisher_to_logger("cm")    # calibration manager
    sm_logger = attach_publisher_to_logger("sm")    # sync manager
    polaris._cm.logTestData(polaris._cm.test_data.keys())

    try:
        socket_app = Starlette(routes=[ WebSocketRoute("/ws", socket_handler) ])
        socket_config = uvicorn.Config(socket_app, host=Config.alpaca_restapi_ip_address, port=Config.alpaca_socket_port, log_level="error")
        socket_server = uvicorn.Server(socket_config)
        logger.info(f'==STARTUP== Serving Alpaca Pilot WebSocket on {Config.alpaca_restapi_ip_address}:{Config.alpaca_socket_port}')

        await asyncio.gather(
            lifecycle._wrap(socket_server.serve()),
            lifecycle._wrap(publish_status(polaris)),
            lifecycle._wrap(cleanup_inactive_clients(timeout_seconds=10)),
            lifecycle.wait_for_event()
        )
    except asyncio.CancelledError:
        logger.info("==CANCELLED== Alpaca Pilot WebSocket cancel received.")
    except socket.gaierror as e:
        raise RuntimeError("WebSocket server failed to start due to invalid host.")
    except Exception as e:
        logger.info(f"==EXCEPTION== Alpaca Pilot WebSocket Unhandled exception: {e}")
    finally:
        logger.info("==SHUTDOWN== Alpaca Pilot WebSocket shutting down.")
        if socket_server and socket_server.started:
            socket_server.should_exit = True
            await socket_server.shutdown()


