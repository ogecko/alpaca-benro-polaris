FROM ubuntu:22.04

ARG ASTRO_PLATFORM="ALPACA"

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
        python3 \
        python3-pip \
        software-properties-common \
        vim \
        git \
        tzdata && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

USER ${POLARIS_USER}

ENV POLARIS_DIR=${POLARIS_USER_HOME}/polaris
RUN mkdir ${POLARIS_DIR}
WORKDIR ${POLARIS_DIR}


COPY --chown=${POLARIS_USER}:${POLARIS_USER} ./requirements.txt ${POLARIS_DIR}/requirements.txt

RUN python3 -m pip install -U pip && \
    python3 -m pip install -r requirements.txt
    

COPY --chown=${POLARIS_USER}:${POLARIS_USER} . ${POLARIS_DIR}
COPY --chown=${POLARIS_USER}:${POLARIS_USER} ./docker/entrypointALPACA.sh ${POLARIS_DIR}/entrypointALPACA.sh
COPY --chown=${POLARIS_USER}:${POLARIS_USER} ./docker/entrypointINDI.sh ${POLARIS_DIR}/entrypointINDI.sh

USER $ROOT

RUN if [ "$ASTRO_PLATFORM" = "ALPACA" ]; then \
		mv ${POLARIS_DIR}/entrypointALPACA.sh ${POLARIS_USER_HOME}/entrypoint.sh; \
	else \
		apt-add-repository ppa:mutlaqja/ppa && \ 
		apt-get install -y indi-bin && \
		rm -rf /var/lib/apt/lists/* && \
		apt-get clean && \
		pip install git+https://github.com/MMTObservatory/pyINDI.git && \
		mv ${POLARIS_DIR}/entrypointINDI.sh ${POLARIS_USER_HOME}/entrypoint.sh; \
	fi
	
USER ${POLARIS_USER}

ENTRYPOINT ["/home/polaris/entrypoint.sh"]
