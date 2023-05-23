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
# NOTE using sh in the next two lines to work around
# this bug in poetry 1.5.0: https://github.com/python-poetry/poetry/issues/7959
poetry run sh ./run_tests.sh # Check tests
poetry run sh ./format.sh # Check formatting
poetry run python -m channel_tool validate # Check that configs are valid
