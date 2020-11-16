#! /bin/sh

# This script validates all of the channel configurations.
# It is intended for use on Docker containers; see test-task.yml

set -ex

apk add gcc musl-dev
pip install pipenv
pipenv sync
pipenv run mypy
pipenv run ./channel_tool validate
