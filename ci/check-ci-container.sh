#! /bin/sh

# Check that the test-all script can execute in a Docker container. Run from project root.

docker run -v $PWD:/app -w /app python:3.8-alpine sh ci/test-all.sh
