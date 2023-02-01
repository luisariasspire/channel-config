import shlex
import subprocess
from pathlib import Path

from behave import *


@when("I run '{command}'")
def when_i_run_command(context, command):
    # Str's .split() method does not respect quotes
    # surrounding predicates. Shlex splits the predicates
    # as one entry.
    cmd = shlex.split(command)

    try:
        cwd = context.config_directory.name
    except AttributeError:
        cwd = Path().absolute()
    print(f"Executing {cmd} in {cwd}")
    context.command_result = subprocess.run(cmd, capture_output=True, cwd=cwd)


@then("it should print text containing")
def then_it_should_print(context):
    output = str(context.command_result.stdout, encoding="utf-8")
    pattern = str(context.text).strip()
    assert pattern in output, f"'{pattern}' not in '{output}'"


@then("it should print text containing exactly")
def then_it_should_print_exactly(context):
    output = str(context.command_result.stdout, encoding="utf-8")
    pattern = str(context.text).strip()
    assert pattern == output, f"'{pattern}' is not equal to '{output}'"


@then("it will exit with code '{expected}'")
def then_it_will_exit_with_code(context, expected):
    actual = context.command_result.returncode
    stdout = str(context.command_result.stdout, encoding="utf-8")
    stderr = str(context.command_result.stderr, encoding="utf-8")
    assert int(expected) == actual, (
        f"Exit code {actual} is not {expected}."
        f" stdout:\n{stdout}\nstderr:\n{stderr}"
    )
