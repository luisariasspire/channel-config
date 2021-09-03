import os
from contextlib import contextmanager
from pathlib import Path

from behave import *

from util import dump_yaml_file, load_yaml_file


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


@given("a ground station '{gs_id}' in '{env}' with channel '{channel_id}'")
def step_impl(context, gs_id, env, channel_id):
    with cwd_from(context):
        templates = load_yaml_file("templates.yaml")
        config = {channel_id: templates[channel_id]}
        dump_yaml_file(config, os.path.join(env, "gs", f"{gs_id}.yaml"))


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
