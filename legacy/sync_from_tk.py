#! /usr/bin/env python3

# This script generates commands for the channel configuration tool `channel_tool` to edit licenses
# for satellites based on TK configuration. It will disable any channels which are not explicitly
# enabled in TK, though it will not enable ones that are. This is done in order to avoid ordering
# issues and overlapping responsibilities between TK checkboxes.

# To generate and run all of the channel addition commands, use:
# pipenv run python legacy/sync_from_tk.py | xargs -L 1 pipenv run

import argparse
import os.path

import requests
from ruamel.yaml import YAML

from util import lookup

TK_DOMAINS = {"staging": "sbox", "production": "cloud"}

PARSER = argparse.ArgumentParser(
    description="A utility to sync TK settings with channel config."
)
PARSER.add_argument(
    "environment",
    choices=["staging", "production"],
    type=str,
    help="Which environment to configure.",
)

DIRNAME = os.path.dirname(__file__)

with open(os.path.join(DIRNAME, "tk_sync_config.yaml")) as f:
    yaml = YAML()
    GROUP_REQS = yaml.load(f)["requirements"]


# Groups which can be configured for a satellite.
SAT_GROUPS = ["sband", "sband_2200", "dvbs2x", "tracking", "rxo"]

# Groups which can be configured for a ground station.
GS_GROUPS = ["sband", "dvbs2x"]


def tk_url(env):
    env_domain = TK_DOMAINS[env]
    return f"https://theknowledge.{env_domain}.spire.com/v2/"


def load_tk_asset(env, kind):
    r = requests.get(tk_url(env) + kind + "s")
    r.raise_for_status()
    return r.json()


def emit_channel_commands(env, ids, channels, state):
    if not ids:
        return
    id_list = ",".join(ids)
    print(
        f"channel_tool edit {env} {id_list}" f" {channels}" f" --enabled={state} --yes"
    )


def emit_asset_commands(asset_type, id_field, groups, env):
    assets = load_tk_asset(env, asset_type)

    disable_chans = {g: [] for g in groups}
    for asset in assets:
        asset_id = asset[id_field]

        for g in groups:
            if not lookup(GROUP_REQS[asset_type][g], asset):
                disable_chans[g].append(asset_id)

    for chan, disabled_assets in disable_chans.items():
        emit_channel_commands(env, disabled_assets, chan, False)


def main():
    args = PARSER.parse_args()
    emit_asset_commands("satellite", "spire_id", SAT_GROUPS, args.environment)
    emit_asset_commands("groundstation", "gs_id", GS_GROUPS, args.environment)


if __name__ == "__main__":
    main()
