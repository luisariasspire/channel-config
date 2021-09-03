#! /bin/sh

coverage run -m pytest
coverage report
behave --format progress3
