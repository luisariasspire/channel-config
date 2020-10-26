#! /bin/bash

# This script validates all of the channel configurations.

set -ex

pip install pipenv
pipenv install
pipenv run channel_tool validate
