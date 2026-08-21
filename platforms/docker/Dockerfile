FROM ubuntu:22.04

ARG ASTRO_PLATFORM="ALPACA"
ARG PYTHON_VERSION=3.13

###
### Create polaris user.
###

ARG POLARIS_UID=1000
ENV POLARIS_UID=${POLARIS_UID}
ARG POLARIS_GID=1000
ENV POLARIS_GID=${POLARIS_GID}

SHELL ["/bin/bash", "-c"]

ENV POLARIS_USER=polaris
ENV POLARIS_USER_HOME=/home/polaris

RUN groupadd -g ${POLARIS_UID} ${POLARIS_USER} && \
    useradd ${POLARIS_USER} -u ${POLARIS_UID} -g ${POLARIS_GID} -r -m -d ${POLARIS_USER_HOME} -s /bin/bash

###
### Install dependencies.
###
ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=Etc/UTC
RUN apt-get update && \
    apt-get install -y \
        ca-certificates \
        vim \
        git \
        tzdata && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# uv manages its own Python toolchain, so we don't need a system python3 package
# (the project requires Python >=3.13, which Ubuntu 22.04 doesn't ship).
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /usr/local/bin/

USER ${POLARIS_USER}

ENV POLARIS_DIR=${POLARIS_USER_HOME}/alpaca
ENV PATH=${POLARIS_DIR}/.venv/bin:${PATH}
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1

RUN mkdir -p ${POLARIS_DIR}
WORKDIR ${POLARIS_DIR}

RUN uv python install ${PYTHON_VERSION}

# Sync dependencies first so this layer caches independently of source changes.
COPY --chown=${POLARIS_USER}:${POLARIS_USER} pyproject.toml uv.lock ${POLARIS_DIR}/
RUN uv sync --frozen --no-dev --no-install-project --python ${PYTHON_VERSION}

# Now bring in the source (src/ holds the "driver" script stub, driver/ the actual app,
# pilot/dist the built Alpaca Pilot SPA served by app_web.py) and install the project itself.
COPY --chown=${POLARIS_USER}:${POLARIS_USER} src ${POLARIS_DIR}/src
COPY --chown=${POLARIS_USER}:${POLARIS_USER} driver ${POLARIS_DIR}/driver
COPY --chown=${POLARIS_USER}:${POLARIS_USER} pilot/dist ${POLARIS_DIR}/pilot/dist
RUN uv sync --frozen --no-dev --python ${PYTHON_VERSION}

COPY --chown=${POLARIS_USER}:${POLARIS_USER} platforms/docker/entrypoint.sh ${POLARIS_USER_HOME}/entrypoint.sh

USER root

RUN chmod +x ${POLARIS_USER_HOME}/entrypoint.sh

USER ${POLARIS_USER}

# REST API, SocketIO, Pilot HTTP/HTTPS, Alpaca discovery, Stellarium/SynScan, mDNS.
EXPOSE 5555 5556 80 443 32227 10001 5353

ENTRYPOINT ["/home/polaris/entrypoint.sh"]
