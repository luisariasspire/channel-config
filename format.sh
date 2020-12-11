#! /bin/sh

black --exclude "legacy/licensing.py" .
isort .
