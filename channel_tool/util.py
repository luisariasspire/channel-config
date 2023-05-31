import difflib
import os
import subprocess
from copy import deepcopy
from io import StringIO
from typing import Any, List, Mapping, Optional, Union

from ruamel.yaml import YAML
from termcolor import colored

from channel_tool.typedefs import (
    ChannelDefinition,
    Environment,
    GroundStationKind,
    SatelliteKind,
)

SAT_DIR = "sat"
GS_DIR = "gs"

SATELLITE: SatelliteKind = "satellite"
GROUND_STATION: GroundStationKind = "groundstation"

TK_DOMAINS: Mapping[Environment, str] = {"staging": "staging.spire.sh", "production": "cloud.spire.com"}

ENVS = ["staging", "production"]
SCHEMA_FILE = "schema.yaml"
TEMPLATE_FILE = "templates.yaml"

_yaml = YAML()


def info(s: str) -> None:
    print(s)


def warn(s: str) -> None:
    print(colored(s, "yellow"))


def err(s: str) -> None:
    print(colored(s, "red"))


def tk_url(env: Environment) -> str:
    env_domain = TK_DOMAINS[env]
    return f"https://theknowledge.{env_domain}/v2/"


def confirm(msg: str) -> bool:
    print("\a")  # Trigger terminal bell
    response = input(colored(f"{msg} [y/N] ", attrs=["bold"]))
    if response in ["y", "Y"]:
        return True
    else:
        return False


def lookup(path: str, d: Mapping[str, Any]) -> Any:
    """Get a nested path from a dict, given as dot-separated fields."""
    path_elts = path.split(".")
    field: Any = d
    for elt in path_elts:
        if field and elt in field:
            field = field[elt]
        else:
            field = None
            break
    return field


def set_path(path: str, d: Mapping[str, Any], val: Any) -> Mapping[str, Any]:
    """Set a nested path in a dict given as dot-separated fields, creating it if needed."""
    d2 = deepcopy(d)
    path_elts = path.split(".")
    parent: Any = d2
    for elt in path_elts[:-1]:
        if parent is not None:
            if elt not in parent:
                parent[elt] = {}
            parent = parent[elt]
        else:
            raise ValueError(f"Unexpected error: found {parent} at {elt} in {path}")
    parent[path_elts[-1]] = val
    return d2


def get_local_username() -> str:
    return os.getenv("USER") or subprocess.getoutput("whoami") or "Unknown User"


def get_git_revision() -> str:
    return subprocess.getoutput("git rev-parse --short HEAD")


def load_yaml_file(f_name: str) -> Any:
    with open(f_name) as f:
        return load_yaml_value(f)


def load_yaml_value(v: Any) -> Any:
    return _yaml.load(v)


def dump_yaml_string(obj: Optional[Mapping[str, Any]]) -> str:
    with StringIO() as stream:
        _yaml.dump(obj, stream)
        return stream.getvalue()


def dump_yaml_file(data: Any, f_name: str) -> None:
    with open(f_name, mode="w+") as f:
        _yaml.dump(data, f)


def str_to_yaml_map(val: str) -> Mapping[str, Any]:
    v = load_yaml_value(val)
    assert isinstance(v, dict), "Expected YAML key-value mapping"
    return v


def file_to_yaml_map(path: str) -> Mapping[str, Any]:
    v = load_yaml_file(path)
    assert isinstance(v, dict), "Expected YAML key-value mapping"
    return v


def str_to_yaml_list(val: str) -> List[Any]:
    v = load_yaml_value(val)
    assert isinstance(v, list), "Expected YAML array"
    return v


def file_to_yaml_list(path: str) -> List[Any]:
    v = load_yaml_file(path)
    assert isinstance(v, list), "Expected YAML array"
    return v


def str_to_yaml_collection(val: str) -> Union[Mapping[str, Any], List[Any]]:
    v = load_yaml_value(val)
    assert isinstance(v, list) or isinstance(
        v, dict
    ), "Expected YAML collection (map or list)"
    return v


def file_to_yaml_collection(path: str) -> Union[Mapping[str, Any], List[Any]]:
    v = load_yaml_file(path)
    assert isinstance(v, list) or isinstance(
        v, dict
    ), "Expected YAML collection (map or list)"
    return v


def str_to_list(values: str) -> List[str]:
    return values.split(",")


def str_to_bool(val: str) -> bool:
    if val.lower() in ["y", "yes", "true", "1"]:
        return True
    if val.lower() in ["n", "no", "false", "0"]:
        return False
    raise ValueError(f"Unrecognized input '{val}'")


def color_diff_line(line: str) -> str:
    if line.startswith("-"):
        return colored(line, "red")
    elif line.startswith("+"):
        return colored(line, "green")
    elif line.startswith("@@ "):
        return colored(line, "blue")
    else:
        return line


def format_diff(
    existing: Optional[ChannelDefinition], new: Optional[ChannelDefinition]
) -> str:
    a = dump_yaml_string(existing).splitlines(keepends=True)
    b = dump_yaml_string(new).splitlines(keepends=True)
    lines = max(len(a), len(b))  # Show all context
    d = difflib.unified_diff(a, b, n=lines)
    cd = [color_diff_line(l) for l in d]
    return "".join(cd)
