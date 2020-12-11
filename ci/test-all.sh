#! /bin/sh

# This script validates all of the channel configurations.
# It is intended for use on Docker containers; see test-task.yml

set -ex

apk add gcc musl-dev
pip install pipenv
pipenv sync --dev

pipenv run mypy # Check types
pipenv run format # Check formatting
pipenv run channel_tool validate # Check that configs are valid
# Check configs are representable in TK, no network I/O
pipenv run sync_to_tk staging --check-only
pipenv run sync_to_tk production --check-only
