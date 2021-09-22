import os
from contextlib import contextmanager
from pathlib import Path

from behave import *

from util import TEMPLATE_FILE, dump_yaml_file, load_yaml_file
from validation import validate_file

ASSET_TYPE_TO_PATH = {"ground station": "gs", "satellite": "sat"}
TEST_ENV = "staging"


@contextmanager
def cwd_from(context):
    try:
        cwd = context.config_directory.name
    except AttributeError:
        cwd = None
    origin = Path().absolute()
    try:
        os.chdir(cwd)
        yield
    finally:
        os.chdir(origin)


@given("the {asset_type} '{id}' has '{channel_id}' {state} in its configuration file")
@given("the {asset_type} '{id}' has '{channel_id}' in its configuration file")
def step_impl(context, asset_type, id, channel_id, state="enabled"):
    state_to_bool = {"enabled": True, "disabled": False}
    with cwd_from(context):
        templates = load_yaml_file(TEMPLATE_FILE)
        config = {channel_id: templates[channel_id]}
        config[channel_id]["enabled"] = state_to_bool[state]
        config_path = os.path.join(
            TEST_ENV, ASSET_TYPE_TO_PATH[asset_type], f"{id}.yaml"
        )
        dump_yaml_file(config, config_path)


@given("there is no configuration for the {asset_type} '{id}'")
def step_impl(context, asset_type, id):
    with cwd_from(context):
        config_path = os.path.join(
            TEST_ENV, ASSET_TYPE_TO_PATH[asset_type], f"{id}.yaml"
        )
        assert not os.path.exists(
            config_path
        ), f"The file {config_path} should not exist"


@step("there is a valid configuration for the {asset_type} '{id}'")
def step_impl(context, asset_type, id):
    with cwd_from(context):
        config_path = os.path.join(
            TEST_ENV, ASSET_TYPE_TO_PATH[asset_type], f"{id}.yaml"
        )
        validate_file(config_path)


def load_config(asset_type, id, env):
    config_path = os.path.join(env, ASSET_TYPE_TO_PATH[asset_type], f"{id}.yaml")
    return load_yaml_file(config_path)


@then("the configuration for the {asset_type} '{id}' will have no enabled channels")
def step_impl(context, asset_type, id):
    with cwd_from(context):
        config = load_config(asset_type, id, TEST_ENV)
        for (chan_id, chan) in config.items():
            assert not chan[
                "enabled"
            ], f"Channel {chan_id} is enabled but should not be"


@then("the channel '{channel}' on {asset_type} '{id}' will be marked legal")
def step_impl(context, channel, asset_type, id):
    with cwd_from(context):
        config = load_config(asset_type, id, TEST_ENV)
        chan = config[channel]
        assert chan["legal"], f"Channel {channel} is not marked legal but should be"


@then("the channel '{channel}' on {asset_type} '{id}' will be marked enabled")
def step_impl(context, channel, asset_type, id):
    with cwd_from(context):
        config = load_config(asset_type, id, TEST_ENV)
        chan = config[channel]
        assert chan["enabled"], f"Channel {channel} is not marked enabled but should be"


@then("the channel '{channel}' on {asset_type} '{id}' will be marked disabled")
def step_impl(context, channel, asset_type, id):
    with cwd_from(context):
        config = load_config(asset_type, id, TEST_ENV)
        chan = config[channel]
        assert not chan[
            "enabled"
        ], f"Channel {channel} is marked enabled but should not be"


@given("a file '{file_path}' containing")
def step_impl(context, file_path):
    with cwd_from(context):
        with open(file_path, mode="w+") as f:
            f.write(context.text)


@then("the file '{file_path}' will contain")
def step_impl(context, file_path):
    with cwd_from(context):
        pattern = str(context.text).strip()
        with open(file_path, mode="r") as f:
            contents = f.read()
            assert pattern in contents, f"{pattern}\nis not in:\n{contents}"


@given("the file '{file_path}' exists")
def step_impl(context, file_path):
    with cwd_from(context):
        assert os.path.exists(file_path), f"{file_path} does not exist"
