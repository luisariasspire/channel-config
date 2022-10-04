#! /bin/sh

# This script validates all of the channel configurations.
# It is intended for use on Docker containers; see test-task.yml

set -ex

export CI=1

apk add gcc musl-dev libffi-dev
pip install poetry
poetry install

# Static checks
poetry run mypy # Check types
poetry run ./run_tests.sh # Check tests
poetry run ./format.sh # Check formatting
poetry run ./channel_tool.py validate # Check that configs are valid
