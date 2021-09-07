#! /bin/sh

# This script validates all of the channel configurations.
# It is intended for use on Docker containers; see test-task.yml

set -ex

apk add gcc musl-dev
pip install pipenv
pipenv sync --dev

# Static checks
pipenv run mypy # Check types
pipenv run tests # Check tests
pipenv run format # Check formatting
pipenv run channel_tool validate # Check that configs are valid
