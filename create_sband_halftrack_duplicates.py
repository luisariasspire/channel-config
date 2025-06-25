"""This script will create a SBAND HALFTRACK version of all SBAND channels on the GS side with appropriate adcs_config.

Originally the default will be for LACUNA, but we can move primary+secondary instrument over to the satellite side once the configs have matured.

Satellite templates are also modified.

All HALFTRACK channels are set as enabled: false.
"""

import argparse
import os
from copy import deepcopy
from enum import Enum
from typing import Any, List

from ruamel.yaml import YAML

_yaml = YAML()

DEFAULT_ADCS_CONFIG = {
    "mode": "NADIRPOINTLATLON",
}


def load_yaml_file(f_name: str) -> Any:
    with open(f_name) as f:
        return load_yaml_value(f)


def load_yaml_value(v: Any) -> Any:
    return _yaml.load(v)


def dump_yaml_file(data: Any, f_name: str) -> None:
    with open(f_name, mode="w+") as f:
        _yaml.dump(data, f)


def create_sband_halftrack(fname: str, gs: bool = False) -> Any:
    """Create HALFTRACK version of each SBAND channel in a channel config file with appropriate config."""
    print(f"modifying {fname}...")
    data = load_yaml_file(fname)
    for channel in list(data.keys()):
        if channel.startswith("S_") and not channel.endswith("_HALFTRACK"):
            dup_channel = f"{channel}_HALFTRACK"
            data[dup_channel] = deepcopy(data[channel])
            if gs:
                if "classification_annotations" in data[dup_channel].keys():
                    data[dup_channel]["classification_annotations"][
                        "adcs_pointing"
                    ] = "HALFTRACK"
                wps = data[dup_channel].setdefault(
                    "window_parameters", {"adcs_config": deepcopy(DEFAULT_ADCS_CONFIG)}
                )
                wps["adcs_config"] = deepcopy(DEFAULT_ADCS_CONFIG)
                dwps = data[dup_channel].setdefault(
                    "dynamic_window_parameters", {"adcs_config_target_coords": True}
                )
                dwps["adcs_config_target_coords"] = True
    return data


def check_halftrack_consistency(fname, gs: bool = False) -> Any:
    """Check that for each SBAND channel in a config, the HALFTRACK version exists and
    the entries are the same except from the modications above."""
    print(f"Checking {fname}...")
    data = load_yaml_file(fname)
    for channel in list(data.keys()):
        if channel.startswith("S_") and not channel.endswith("_HALFTRACK"):
            channel_data = data[channel]
            dup_channel = f"{channel}_HALFTRACK"
            dup_channel_data = data.get(dup_channel, None)

            # HALFTRACK version of SBAND doesn't exist
            if not dup_channel_data:
                raise Exception("No HALFTRACK channel present")

            # Check that the halftrack and original SBAND are the same aside from modifications.
            if gs:
                if isinstance(dup_channel_data.get("window_parameters"), dict):
                    dup_channel_data["window_parameters"].pop("adcs_config", None)
                if not isinstance(channel_data.get("window_parameters"), dict):
                    dup_channel_data.pop("window_parameters", None)
                if isinstance(dup_channel_data.get("dynamic_window_parameters"), dict):
                    dup_channel_data["dynamic_window_parameters"].pop(
                        "adcs_config_target_coords", None
                    )
                if not isinstance(channel_data.get("dynamic_window_parameters"), dict):
                    dup_channel_data.pop("dynamic_window_parameters", None)
                if isinstance(dup_channel_data.get("classification_annotations"), dict):
                    dup_channel_data["classification_annotations"].pop(
                        "adcs_pointing", None
                    )
                if isinstance(channel_data.get("classification_annotations"), dict):
                    channel_data["classification_annotations"].pop(
                        "adcs_pointing", None
                    )

            if channel_data == dup_channel_data:
                print(f"{fname} - {channel} - PASSED")
            else:
                raise Exception(f"{fname} - {channel} - FAILED")


class Mode(Enum):
    RUN_AND_CHECK = "run_and_check"
    CHECK_ONLY = "check_only"

    def __str__(self):
        return self.value


def check_all_consistency(gs_fnames: List[str], sat_template_fname: str):
    for gs_fname in gs_fnames:
        check_halftrack_consistency(gs_fname, True)
    check_halftrack_consistency(sat_template_fname, False)


def run(mode: Mode):
    gs_fnames = (
        [f"staging/gs/{f}" for f in os.listdir("staging/gs/")]
        + [f"production/gs/{f}" for f in os.listdir("production/gs/")]
        + ["gs_templates.yaml"]
    )
    sat_template_fname = "sat_templates.yaml"

    if mode == Mode.RUN_AND_CHECK:
        print("Creating HALFTRACK channels and checking consistency...")
        for gs_fname in gs_fnames:
            data = create_sband_halftrack(gs_fname, True)
            dump_yaml_file(data, gs_fname)
        data = create_sband_halftrack(sat_template_fname, False)
        dump_yaml_file(data, sat_template_fname)
        check_all_consistency(gs_fnames, sat_template_fname)
    elif mode == Mode.CHECK_ONLY:
        print("Checking consistency only...")
        check_all_consistency(gs_fnames, sat_template_fname)
    else:
        raise ValueError(f"Unhandled mode: {mode}")


def main():
    parser = argparse.ArgumentParser(description="Run script in different modes.")
    parser.add_argument(
        "--mode",
        type=Mode,
        choices=list(Mode),
        required=True,
        help="Select the mode: 'run_and_check' or 'check_only'",
    )
    args = parser.parse_args()
    run(args.mode)


if __name__ == "__main__":
    main()
