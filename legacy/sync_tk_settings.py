#! /usr/bin/env python3

# This script generates commands for the channel configuration tool `channel_tool` to edit licenses
# for satellites based on TK configuration. It will disable any channels which are not explicitly
# enabled in TK, though it will not enable ones that are. This is done in order to avoid ordering
# issues and overlapping responsibilities between TK checkboxes.

# To generate and run all of the channel addition commands, use:
# pipenv run python legacy/sync_tk_settings.py | xargs -L 1 pipenv run

import argparse
import requests

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


def tk_url(env):
    env_domain = TK_DOMAINS[env]
    return f"https://theknowledge.{env_domain}.spire.com/v2/"


def load_tk_asset(env, kind):
    r = requests.get(tk_url(env) + kind)
    r.raise_for_status()
    return r.json()


def emit_channel_commands(env, ids, channels, state):
    if not ids:
        return
    id_list = ",".join(ids)
    print(
        f"channel_tool edit {env} {id_list}"
        f" {channels}"
        f" --enabled={state} --yes"
    )


def emit_sat_commands(env):
    satellites = load_tk_asset(env, "satellites")

    disable_chans = {
        "sband": [],
        "sband_2200": [],
        "dvb": [],
        "tracking": [],
        "rxo": [],
    }
    for sat in satellites:
        spire_id = sat["spire_id"]

        if not sat["sband_enabled"]:
            disable_chans["sband"].append(spire_id)

        if not sat["sband_2200mhz"]:
            disable_chans["sband_2200"].append(spire_id)

        if not sat["dvbs2x_enabled"]:
            disable_chans["dvb"].append(spire_id)

        if not sat["target_tracking_enabled"]:
            disable_chans["tracking"].append(spire_id)

        if not sat.get("pipeline") or not sat["pipeline"].get("enable_rxo", False):
            disable_chans["rxo"].append(spire_id)

    for chan, disable_sats in disable_chans.items():
        emit_channel_commands(env, disable_sats, chan, False)


def emit_gs_commands(env):
    groundstations = load_tk_asset(env, "groundstations")

    disable_chans = {
        "sband": [],
        "dvb": [],
    }
    for gs in groundstations:
        gs_id = gs["gs_id"]

        if not gs["sband_enabled"]:
            disable_chans["sband"].append(gs_id)

        if not gs["dvbs2x_enabled"]:
            disable_chans["dvb"].append(gs_id)

    for chan, disable_gs in disable_chans.items():
        emit_channel_commands(env, disable_gs, chan, False)


def main():
    args = PARSER.parse_args()
    emit_sat_commands(args.environment)
    emit_gs_commands(args.environment)


if __name__ == "__main__":
    main()
