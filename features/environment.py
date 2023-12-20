"""
    Fixtures and support code for setting up BDD testing environments.
"""

import os
import tempfile
from pathlib import Path

from behave import fixture, use_fixture


@fixture
def config_isolated(context):
    """Create an isolated configuration tree with basic structure for use in tests."""
    origin = Path().absolute()
    context.config_directory = tempfile.TemporaryDirectory()
    dir_name = context.config_directory.name
    os.makedirs(os.path.join(dir_name, "staging", "gs"))
    os.makedirs(os.path.join(dir_name, "staging", "sat"))
    install_symlinks(
        [
            "Pipfile",
            "Pipfile.lock",
            "channel_tool",
            "contact_type_defs.yaml",
            "sat_license_defs.yaml",
            "schema.yaml",
            "templates.yaml",
            "asset_groups.yaml",
        ],
        origin,
        dir_name,
    )
    yield context.config_directory.name
    context.config_directory.cleanup()


def install_symlinks(files, origin, dir_name):
    for f in files:
        source = os.path.join(origin, f)
        target = os.path.join(dir_name, f)
        os.symlink(source, target)


def before_tag(context, tag):
    if tag == "fixture.config.isolated":
        use_fixture(config_isolated, context)
