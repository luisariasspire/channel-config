import os
import subprocess
from copy import deepcopy
from typing import Any, Mapping

from termcolor import colored

from typedefs import Environment, GroundStationKind, SatelliteKind

SAT_DIR = "sat"
GS_DIR = "gs"

SATELLITE: SatelliteKind = "satellite"
GROUND_STATION: GroundStationKind = "groundstation"

TK_DOMAINS: Mapping[Environment, str] = {"staging": "sbox", "production": "cloud"}


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
    """Get a nested path from a dict, given as dot-separated fields."""
    d2 = deepcopy(d)
    path_elts = path.split(".")
    parent: Any = d2
    for elt in path_elts[:-1]:
        if parent and elt in parent:
            parent = parent[elt]
        else:
            raise ValueError("No field {path} in object {d}")
    parent[path_elts[-1]] = val
    return d2


def get_local_username() -> str:
    return os.getenv("USER") or subprocess.getoutput("whoami") or "Unknown User"


def get_git_revision() -> str:
    return subprocess.getoutput("git rev-parse --short HEAD")
