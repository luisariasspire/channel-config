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


def config_path(asset_type, id):
    return os.path.join(TEST_ENV, ASSET_TYPE_TO_PATH[asset_type], f"{id}.yaml")


def load_config(asset_type, id, env):
    return load_yaml_file(config_path(asset_type, id))


@given("the {asset_type} '{id}' has '{channel_id}' {state} in its configuration file")
@given("the {asset_type} '{id}' has '{channel_id}' in its configuration file")
def has_channel_with_state(context, asset_type, id, channel_id, state="enabled"):
    state_to_bool = {"enabled": True, "disabled": False}
    with cwd_from(context):
        templates = load_yaml_file(TEMPLATE_FILE)
        config = {channel_id: templates[channel_id]}
        config[channel_id]["enabled"] = state_to_bool[state]
        dump_yaml_file(config, config_path(asset_type, id))


@then("the {asset_type} '{id}' has '{channel_id}' in its configuration file")
def has_channel(context, asset_type, id, channel_id):
    with cwd_from(context):
        assert channel_id in load_config(asset_type, id, TEST_ENV)


@given("the {asset_type} '{id}' does not have '{channel_id}' in its configuration file")
def does_not_have_channel(context, asset_type, id, channel_id):
    with cwd_from(context):
        config = load_config(asset_type, id, TEST_ENV)
        try:
            del config[channel_id]
        except KeyError:
            pass
        dump_yaml_file(config, config_path(asset_type, id))


@given("there is no configuration for the {asset_type} '{id}'")
def has_no_config(context, asset_type, id):
    with cwd_from(context):
        assert not os.path.exists(
            config_path(asset_type, id)
        ), f"The file {config_path} should not exist"


@step("there is a valid configuration for the {asset_type} '{id}'")
def has_config(context, asset_type, id):
    with cwd_from(context):
        validate_file(config_path(asset_type, id))


@then("the configuration for the {asset_type} '{id}' will have no enabled channels")
def has_no_enabled_channels(context, asset_type, id):
    with cwd_from(context):
        config = load_config(asset_type, id, TEST_ENV)
        for (chan_id, chan) in config.items():
            assert not chan[
                "enabled"
            ], f"Channel {chan_id} is enabled but should not be"


@then("the channel '{channel}' on {asset_type} '{id}' will be marked legal")
def has_legal_channel(context, channel, asset_type, id):
    with cwd_from(context):
        config = load_config(asset_type, id, TEST_ENV)
        chan = config[channel]
        assert chan["legal"], f"Channel {channel} is not marked legal but should be"


@then("the channel '{channel}' on {asset_type} '{id}' will be marked enabled")
def has_enabled_channel(context, channel, asset_type, id):
    with cwd_from(context):
        config = load_config(asset_type, id, TEST_ENV)
        chan = config[channel]
        assert chan["enabled"], f"Channel {channel} is not marked enabled but should be"


@then("the channel '{channel}' on {asset_type} '{id}' will be marked disabled")
def has_disabled_channel(context, channel, asset_type, id):
    with cwd_from(context):
        config = load_config(asset_type, id, TEST_ENV)
        chan = config[channel]
        assert not chan[
            "enabled"
        ], f"Channel {channel} is marked enabled but should not be"


@then("the channel '{channel}' on {asset_type} '{id}' has {property} set to {value}")
def has_channel_with_property(context, channel, asset_type, id, property, value):
    with cwd_from(context):
        config = load_config(asset_type, id, TEST_ENV)
        chan = config[channel]
        assert (
            property in chan
        ), f"Property {property} doesn't exist on channel {channel}"
        actual = chan[property]
        assert (
            actual == value
        ), f"Property {property} on channel {channel} has value {actual}, expected {value}"


@given("a file '{file_path}' containing")
def create_file_containing(context, file_path):
    with cwd_from(context):
        with open(file_path, mode="w+") as f:
            f.write(context.text)


@then("the file '{file_path}' will contain")
def file_contains(context, file_path):
    with cwd_from(context):
        pattern = str(context.text).strip()
        with open(file_path, mode="r") as f:
            contents = f.read()
            assert pattern in contents, f"{pattern}\nis not in:\n{contents}"


@given("the file '{file_path}' exists")
def create_empty_file(context, file_path):
    with cwd_from(context):
        assert os.path.exists(file_path), f"{file_path} does not exist"
