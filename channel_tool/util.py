import os
import subprocess
from copy import deepcopy
from io import StringIO
from typing import Any, Mapping, Optional

from ruamel.yaml import YAML
from termcolor import colored

from channel_tool.typedefs import Environment, GroundStationKind, SatelliteKind

SAT_DIR = "sat"
GS_DIR = "gs"

SATELLITE: SatelliteKind = "satellite"
GROUND_STATION: GroundStationKind = "groundstation"

TK_DOMAINS: Mapping[Environment, str] = {"staging": "sbox", "production": "cloud"}

ENVS = ["staging", "production"]
SCHEMA_FILE = "schema.yaml"
TEMPLATE_FILE = "templates.yaml"

_yaml = YAML()


def tk_url(env: Environment) -> str:
    env_domain = TK_DOMAINS[env]
    return f"https://theknowledge.{env_domain}.spire.com/v2/"


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
