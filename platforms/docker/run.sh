#!/usr/bin/env bash

SCRIPT_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
SCRIPT_NAME="${0}"

POLARIS_REGISTRY=docker.io/library

POLARIS_IMAGE_NAME=polaris
POLARIS_IMAGE_VERSION=latest
POLARIS_IMAGE_FULL=${POLARIS_REGISTRY}/${POLARIS_IMAGE_NAME}:${POLARIS_IMAGE_VERSION}

# Arguments
DOCKER_BUILD_IMAGE="false"
ASTRO_PLATFORM="ALPACA"

# Set local time zone - choose from TZ identifier listed at 
# https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
if [ -z "${TIME_ZONE}" ]; then TIME_ZONE="Australia/Sydney"; fi

source "${SCRIPT_DIR}/util.sh"


define_usage() {
    local -n define_usage_SCRIPT_NAME="${1:?}"

    read -d '' USAGE <<EOM

Usage: ${define_usage_SCRIPT_NAME} [OPTIONS]

Options:
    -t <TZ>    Set the timezone (default: ${TIME_ZONE})
    -b         Build the image before running.
    -h         Print help and exit.

EOM
}

parse_args() {
    local OPTIND=1

    while getopts ":t:bh" option; do
        case "${option}" in
            "t")
                TIME_ZONE=${OPTARG}
                echo "TIME_ZONE set to ${TIME_ZONE}"
                ;;
            "b")
                DOCKER_BUILD_IMAGE="true"
                echo "Docker build enabled"
                ;;
            "h")
                help_exit "true"
                ;;
            "?")
                echo "Error: invalid option (-${OPTARG})."
                help_exit "false"
                ;;
            ":")
                echo "Error: -${OPTARG} requires an argument."
                help_exit "false"
                ;;
        esac
    done
}


main() {
    docker_build \
        DOCKER_BUILD_IMAGE \
        "true" \
        "${SCRIPT_DIR}/Dockerfile" \
        POLARIS_IMAGE_FULL \
        ASTRO_PLATFORM \
        "${SCRIPT_DIR}/../../"
    if [ $? -ne 0 ]; then
        echo "Docker build failed."
        return 1
    fi

    if [ -z "${TIME_ZONE}" ]; then
        echo "TIME_ZONE has not been set - see arguments in run.sh"
        return 1
    fi

    # data/ holds everything the driver generates or that Alpaca Pilot saves at runtime
    # (config overrides, presets, calibration, TLS certs, ...). Bind-mounting it from the
    # host means it survives container restarts/rebuilds.
    mkdir -p "${SCRIPT_DIR}/data"

    read -d '' DOCKER_RUN_OPTIONS <<EOM
        --mount type=bind,source="${SCRIPT_DIR}/data",target="/home/polaris/alpaca/data" \
        -p 5555:5555 \
        -p 5556:5556 \
        -p 80:80 \
        -p 443:443 \
        -p 32227:32227/udp \
        -p 10001:10001 \
        -p 5353:5353/udp
EOM

    docker_run \
        POLARIS_IMAGE_NAME \
        POLARIS_IMAGE_FULL \
        "${TIME_ZONE}" \
        DOCKER_RUN_OPTIONS
}

# Setup
define_usage SCRIPT_NAME

# Parse arguments
parse_args "${@}"

# Main
main
