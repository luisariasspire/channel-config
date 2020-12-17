#! /bin/sh

black --exclude ".*/licensing.py" .
isort .
