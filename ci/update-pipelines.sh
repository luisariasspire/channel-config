#! /bin/bash

CI_DIR=$(dirname $0)

function set_pipeline {
    echo "Updating $1 to match config in $2"
    fly set-pipeline \
        --target=optimizer \
        --pipeline=$1 \
        --config=$2
}

set_pipeline channel-config-pr "$CI_DIR/pr-pipeline.yml"
