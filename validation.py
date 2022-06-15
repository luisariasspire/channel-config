import os
from typing import Any, Callable, Optional

import jsonschema
from jsonschema.exceptions import ValidationError as SchemaValidationError
from jsonschema.exceptions import best_match
from termcolor import colored

from typedefs import ChannelDefinition
from util import (
    ENVS,
    GROUND_STATION,
    GS_DIR,
    SAT_DIR,
    SATELLITE,
    SCHEMA_FILE,
    load_yaml_file,
)


class ValidationError(Exception):
    def __init__(self, parent, file=None, key=None, count=1):
        self._parent = parent
        self._file = file
        self._key = key
        self._count = count

    def __str__(self):
        return f"""Validation error: {self._parent.message}
        in {self._parent.json_path}

        (Best match of {self._count} errors found while validating {self._file}#{self._key})
        Context:
        {self._parent.context}
        """


def validate_all() -> None:
    for asset_type in [GROUND_STATION, SATELLITE]:
        print(f"Validating {asset_type} templates...")
        validate_file(
            "templates.yaml",
            preprocess=lambda x: filter_properties(asset_type, x),
        )
        print(colored("PASS", "green"))

    for env in ENVS:
        print(f"Validating {env} satellites...")
        sat_dir = os.path.join(env, SAT_DIR)
        all_sats = os.listdir(sat_dir)
        for sf in sorted(all_sats):
            print(f"{sf}... ", end="")
            validate_file(os.path.join(sat_dir, sf))
            print(colored("PASS", "green"))

        print(f"Validating {env} ground stations...")
        gs_dir = os.path.join(env, GS_DIR)
        all_stations = os.listdir(gs_dir)
        for gsf in sorted(all_stations):
            print(f"{gsf}... ", end="")
            validate_file(os.path.join(gs_dir, gsf))
    print("All passed!")


def validate_file(
    cf: str,
    preprocess: Optional[Callable[[ChannelDefinition], ChannelDefinition]] = None,
) -> None:
    config = load_yaml_file(cf)
    for key in config:
        c = config[key]
        if preprocess:
            c = preprocess(c)
        validate_one(c, file=cf, key=key)


def validate_one(config: ChannelDefinition, file: str, key: str) -> None:
    schema = load_schema()
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(config))  # type: ignore
    if errs:
        raise ValidationError(best_match(errs), file=file, key=key, count=len(errs))


# Memoize the JSON Schema definition.
loaded_schema = None


def load_schema() -> Any:
    global loaded_schema
    if not loaded_schema:
        # File has "schema" and "definitions" as top-level fields.
        loaded_schema = load_yaml_file(SCHEMA_FILE)["schema"]
    return loaded_schema


def filter_properties(asset_type: str, chan: ChannelDefinition) -> ChannelDefinition:
    """Filter the channel configuration properties based on the asset type."""
    if chan:
        if asset_type != GROUND_STATION and "ground_station_constraints" in chan:
            del chan["ground_station_constraints"]
        if asset_type != SATELLITE and "satellite_constraints" in chan:
            del chan["satellite_constraints"]
    return chan
