#! /usr/bin/env python3

# Update TK's configuration to match the current channel configs.
#
# This script reads the channel configuration files and sends patch requests to TK to set the
# switches there so that the same channels are enabled in both systems. If this is not possible, it
# emits a warning with the conflict.
#
# To perform a sync, run:
# pipenv run python legacy/sync_to_tk.py
import argparse
import itertools
import os.path
from collections import defaultdict
from typing import (
    Any,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    Set,
    Tuple,
    Union,
    overload,
)

import requests
from ruamel.yaml import YAML
from tabulate import tabulate
from termcolor import colored

from typedefs import (
    AssetConfig,
    AssetKind,
    Environment,
    GroundStationKind,
    SatelliteKind,
    TkGroundStation,
    TkSatellite,
)
from util import (
    GS_DIR,
    SAT_DIR,
    confirm,
    get_git_revision,
    get_local_username,
    lookup,
    set_path,
    tk_url,
)

PARSER = argparse.ArgumentParser(
    description="A utility to sync TK settings with channel config."
)
PARSER.add_argument(
    "environment",
    choices=["staging", "production"],
    type=str,
    help="Which environment to configure.",
)
PARSER.add_argument(
    "--dry-run",
    action="store_true",
    help="Print what would happen but don't make changes.",
)
PARSER.add_argument(
    "--fail-fast",
    action="store_true",
    help="Die fast on errors.",
)
PARSER.add_argument(
    "--yes",
    action="store_true",
    help="Skip confirmation prompts.",
)
PARSER.add_argument(
    "--check-only",
    action="store_true",
    help="Just verify that the settings are representable, don't read from TK.",
)

MISMATCH_COLOR = "magenta"
TRUE_COLOR = "green"
FALSE_COLOR = "red"

DIRNAME = os.path.dirname(__file__)

yaml = YAML()

with open(os.path.join(DIRNAME, "tk_settings_mapping.yaml")) as f:
    GROUP_REQS = yaml.load(f)


with open(os.path.join(DIRNAME, "../contact_type_defs.yaml")) as f:
    GROUP_DEFS: Mapping[str, List[str]] = yaml.load(f)["groups"]


class SettingsConflictError(Exception):
    pass


# Required settings by channel, expanded from group configs.
# A channel requires all of the settings from all of its groups to be on.
CHANNEL_REQS: Mapping[str, Set[str]] = defaultdict(set)

for group, channels in GROUP_DEFS.items():
    required_setting = GROUP_REQS[group]
    if required_setting:
        for channel in channels:
            CHANNEL_REQS[channel].add(required_setting)


@overload
def load_tk_asset(env: Environment, asset: str, kind: SatelliteKind) -> TkSatellite:
    ...


@overload
def load_tk_asset(
    env: Environment, asset: str, kind: GroundStationKind
) -> TkGroundStation:
    ...


def load_tk_asset(
    env: Environment, asset: str, kind: AssetKind
) -> Union[TkSatellite, TkGroundStation]:
    r = requests.get(tk_url(env) + kind + f"/{asset}")
    r.raise_for_status()
    return r.json()  # type: ignore


def patch_tk_asset(
    env: Environment, asset: str, kind: AssetKind, patch: Mapping[str, bool]
) -> None:
    json_patch: Mapping[str, Any] = {}
    for path, val in patch.items():
        json_patch = set_path(path, json_patch, val)

    headers = {
        "User-Agent": f"sync_to_tk.py / {get_git_revision()}",
        "X-Forwarded-User": f"{get_local_username()} via sync_to_tk.py",
    }

    r = requests.patch(tk_url(env) + kind + f"/{asset}", json=patch, headers=headers)
    r.raise_for_status()


# TODO This can probably be combined with some code in channel_tool.py.
def find_asset_configs(
    env: Environment,
) -> Iterable[Tuple[str, AssetKind, AssetConfig]]:
    for kind, subdir in [("satellite", SAT_DIR), ("groundstation", GS_DIR)]:
        dirpath = os.path.join(env, subdir)
        assets = sorted(os.listdir(dirpath))
        for af in assets:
            with open(os.path.join(dirpath, af), "r") as yaml_file:
                cfg = yaml.load(yaml_file)
                asset_id = os.path.splitext(os.path.basename(af))[0]
                yield (asset_id, kind, cfg)  # type: ignore


def generate_settings_requirements(
    cfg: AssetConfig, channel_reqs: Mapping[str, Set[str]]
) -> Tuple[Set[str], Set[FrozenSet[str]]]:
    """Create the TK settings requirements for this asset config.

    This function produces two sets. The first is a set of settings which must be turned on for this
    config's enabled channels to be enabled by TK. The second is a set of sets, each of which
    contains settings which may be disabled to turn off the channels which are disabled in the
    asset's configuration.

    Said another way: for TK to be configured properly with regards to this asset, all of the
    settings in the first set must be on, and at least one of the settings in each of the subsets of
    the second set must be turned off.
    """
    ons = set()
    offs = set()
    for channel, chan_cfg in cfg.items():
        if chan_cfg and chan_cfg["enabled"]:
            ons.update(CHANNEL_REQS[channel])
        else:
            offs.add(frozenset(CHANNEL_REQS[channel]))
    return ons, offs


def refine(
    ons: Set[str], offs: Set[FrozenSet[str]]
) -> Tuple[Set[str], Set[FrozenSet[str]]]:
    off_options = [list(opts) for opts in offs]
    conflicts = set()
    for setting in ons:
        for off_opt in off_options:
            if setting in off_opt:
                off_opt.remove(setting)
                conflicts.add(setting)
            if not off_opt:
                # We have exhausted all of the settings for this set which may be turned off.
                raise SettingsConflictError(
                    f"Incompatible settings!\n"
                    f"Each of these settings must be both enabled and disabled at the same time:\n"
                    f"{conflicts}"
                )

    # If we make it here, then there are options to turn off all the settings that need to be turned
    # off and so there are no conflicts. The remaining on and off sets are disjoint and non-empty.
    refined_offs: Set[FrozenSet[str]] = set()
    refined_offs.update([frozenset(os) for os in off_options])
    return ons, refined_offs


def create_patch_for_asset(
    asset_data: Mapping[str, Any], enabled: Set[str], disabled: Set[FrozenSet[str]]
) -> Tuple[Mapping[str, Any], Mapping[str, bool]]:

    fieldset: Dict[str, Any] = {}
    patch: Dict[str, bool] = {}

    for s in enabled:
        f = lookup(s, asset_data)
        fieldset[s] = f
        if not f:
            patch[s] = True

    disable_requests = set()
    for opts in disabled:
        want_off = set()
        for s in opts:
            f = lookup(s, asset_data)
            fieldset[s] = f
            if f:
                want_off.add(s)

        # Check if there is at least one field in our set of options which is already disabled. We
        # just need one. If not, add the fields which can be flipped to the "off-request" set.
        if not any([not lookup(s, asset_data) for s in opts]):
            disable_requests.add(frozenset(want_off))

    # Reduce the set of sets to produce a minimal patch.
    min_offs = sorted(
        [set(x) for x in itertools.product(*disable_requests)], key=lambda x: len(x)
    )
    for f in min_offs[0]:
        patch[f] = False

    return fieldset, patch


def confirm_patch(
    asset: str,
    existing: Mapping[str, Any],
    patch: Mapping[str, bool],
    cfg: AssetConfig,
    yes: bool,
) -> bool:
    print("Mismatch.\n")
    print(f"The TK settings for {asset} need to be updated with:\n")
    for s, v in existing.items():
        if s in patch:
            p = patch[s]
            print("    ", end="")  # Add spacing without text properties
            print(colored(f"{s} == {v} -> {p}", MISMATCH_COLOR, attrs=["underline"]))
        else:
            print(f"    {s} == {v}")

    print()
    print("... because TK's flags don't match its channel configuration:")

    def bold(s: str) -> str:
        return colored(s, attrs=["bold"])

    # TODO Extract this logic and use it to explain conflicts as well as nominal changes
    enabled_statuses = [
        (bold("Channel (* = Mismatch)"), bold("State"), bold("Required TK settings"))
    ]
    for chan, chan_cfg in cfg.items():
        assert chan_cfg is not None
        needs_patch = any([req in patch for req in CHANNEL_REQS[chan]])

        def highlight(s: str) -> str:
            if needs_patch:
                return colored(s, MISMATCH_COLOR, attrs=["bold"])
            else:
                return s

        chan_name = highlight(chan + " *" if needs_patch else chan)
        state = "Enabled" if chan_cfg["enabled"] else "Disabled"

        settings = "n/a"
        reqs = ", ".join(
            {
                highlight(req + "*") if req in patch else req
                for req in CHANNEL_REQS[chan]
            }
        )
        if chan_cfg["enabled"]:
            settings = f"All of {reqs} " + highlight("are True") if reqs else "n/a"
        else:
            settings = f"One of {reqs} " + highlight("is False") if reqs else "n/a"

        enabled_statuses.append((highlight(chan_name), state, settings))

    print(tabulate(enabled_statuses))

    print()
    if not yes:
        return confirm(f"Update {asset} in TK?")
    else:
        print(bold("Confirmation skipped because --yes option was given."))
        return True


def main() -> None:
    args = PARSER.parse_args()
    print(
        f"sync_to_tk.py | version {get_git_revision()} | running as {get_local_username()}"
    )

    if args.dry_run:
        print("Running in dry run mode. No writes will be performed.")
    if args.yes:
        print("User gave --yes option, skipping confirmation prompts.")

    clean_run = True

    for (asset, kind, cfg) in find_asset_configs(args.environment):
        print(f"\rChecking {asset}...    ", end="")
        raw_enabled, raw_disabled = generate_settings_requirements(cfg, CHANNEL_REQS)
        try:
            enabled, disabled = refine(raw_enabled, raw_disabled)

            if args.check_only:
                continue  # We're just verifying that the settings are representable.

            asset_data = load_tk_asset(args.environment, asset, kind)
            existing, patch = create_patch_for_asset(asset_data, enabled, disabled)
            if patch:
                if confirm_patch(asset, existing, patch, cfg, args.yes):
                    if not args.dry_run:
                        patch_tk_asset(args.environment, asset, kind, patch)
                    else:
                        print("(Skipped for dry run)")
                else:
                    print("Canceled.")
        except Exception as e:
            clean_run = False
            print(colored(f"\nError updating {asset}: {e}", "red", attrs=["bold"]))
            if args.fail_fast:
                raise e

    if not clean_run:
        exit(1)


if __name__ == "__main__":
    main()
