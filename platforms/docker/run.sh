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
    -t <TZ>, --timezone=<TZ>    Set the timezone (default: ${TIME_ZONE})
    -b, --build                 Build the image before running.
    -h, --help                  Print help and exit.

EOM
}

parse_args() {
    local OPTIND

    while getopts_long "biht: build indi help timezone:" option "${@}"; do
        case "${option}" in
            "t" | "timezone")
                TIME_ZONE=${OPTARG}
                echo "TIME_ZONE set to ${TIME_ZONE}"
                ;;
            "b" | "build")
                DOCKER_BUILD_IMAGE="true"
                echo "Docker build enabled"
                ;;
            "h" | "help")
                help_exit "true"
                ;;
            "?")
                echo "Error: invalid option (${OPTARG})."
                help_exit "false"
                ;;
            ":")
                echo "Error: -${OPTARG} requires an argument."
                help_exit "false"
                ;;
            *)
                help_exit "false"
                ;;
        esac
    done
    shift $(( OPTIND - 1 ))
}


main() {
    if [ ! -f "${SCRIPT_DIR}/driver/main.py" ]; then
        cp -r ${SCRIPT_DIR}/../../driver ${SCRIPT_DIR}
    fi
    docker_build \
        DOCKER_BUILD_IMAGE \
        "true" \
        "${SCRIPT_DIR}/Dockerfile" \
        POLARIS_IMAGE_FULL \
        ASTRO_PLATFORM \
        "${SCRIPT_DIR}/../"

    if [ ! -f "${SCRIPT_DIR}/config.toml" ]; then
        echo "S{SCRIPT_DIR}/config.toml doesn't exist.  Copy and customize ${SCRIPT_DIR}/config.toml.example."
        return 1
    fi


    if [ -z "${TIME_ZONE}" ]; then
        echo "TIME_ZONE has not been set - see arguments in run.sh"
        return 1
    fi
    
    read -d '' DOCKER_RUN_OPTIONS <<EOM
        --mount type=bind,source="${SCRIPT_DIR}/config.toml",target="/home/polaris/aplaca/device/config.toml" \
        -p 5432:5432 \
        -p 5555:5555
EOM

    docker_run \
        POLARIS_IMAGE_NAME \
        POLARIS_IMAGE_FULL \
        "${TIME_ZONE}" \
        DOCKER_RUN_OPTIONS
}

# Setup
setup SCRIPT_DIR SCRIPT_NAME

# Parse arguments
parse_args "${@}"
shift $(( OPTIND - 1 ))

# Main
main
