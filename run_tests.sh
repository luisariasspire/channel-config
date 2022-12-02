#! /bin/sh

mypy
coverage run -m pytest
coverage report
behave --format progress3
