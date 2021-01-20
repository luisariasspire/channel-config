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
import os.path
from collections import defaultdict
from typing import (
    Any,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Sequence,
    Set,
    Optional,
    Tuple,
    TypedDict,
    Union,
    overload,
)

import requests
from more_itertools import powerset
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
    GROUND_STATION,
    GS_DIR,
    SAT_DIR,
    SATELLITE,
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
    "--kind",
    choices=["satellite", "groundstation"],
    type=str,
    help="Limit changes to a given type of asset.",
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

with open(os.path.join(DIRNAME, "tk_sync_config.yaml")) as f:
    cfg = yaml.load(f)
    GROUP_REQS = cfg["requirements"]
    SKIP_CHANS = cfg["skip_channels"]


with open(os.path.join(DIRNAME, "../contact_type_defs.yaml")) as f:
    GROUP_DEFS: Mapping[str, List[str]] = yaml.load(f)["groups"]


class SettingsConflictError(Exception):
    pass


# Type for conjunctive normal form representation of TK settings
class CnfClause(NamedTuple):
    defn: FrozenSet[Tuple[str, bool]]
    comment: str


CnfFormula = Set[CnfClause]


class SkipChan(TypedDict):
    channel: str
    comment: str


# Required settings by channel, expanded from group configs.
# A channel requires all of the settings from all of its groups to be on.
CHANNEL_REQS: Mapping[AssetKind, Mapping[str, Set[str]]] = defaultdict(
    lambda: defaultdict(set)
)

kinds: List[AssetKind] = [SATELLITE, GROUND_STATION]
for kind in kinds:
    for group, channels in GROUP_DEFS.items():
        required_setting = GROUP_REQS[kind][group]
        if required_setting:
            for channel in channels:
                CHANNEL_REQS[kind][channel].add(required_setting)


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
    kind: Optional[str],
) -> Iterable[Tuple[str, AssetKind, AssetConfig]]:
    for k, subdir in [("satellite", SAT_DIR), ("groundstation", GS_DIR)]:
        # Filter assets by kind if requested
        if kind and kind != k:
            continue
        dirpath = os.path.join(env, subdir)
        assets = sorted(os.listdir(dirpath))
        for af in assets:
            with open(os.path.join(dirpath, af), "r") as yaml_file:
                cfg = yaml.load(yaml_file)
                asset_id = os.path.splitext(os.path.basename(af))[0]
                yield (asset_id, k, cfg)  # type: ignore


def generate_settings_requirements(
    cfg: AssetConfig,
    channel_reqs: Mapping[str, Set[str]],
    skip_channels: Sequence[SkipChan],
) -> CnfFormula:
    """Create the TK settings requirements for this asset config.

    This function produces a set of sets, describing the TK settings requirements for this
    asset. For TK to be correctly configured, at least one setting from each of the sub-sets must be
    true. This is an "and-of-ors" representation (i.e. conjunctive normal form).

    """
    clauses: CnfFormula = set()

    def _eval(term: str) -> Tuple[str, bool]:
        name = term
        inverted = False
        if term.startswith("not "):
            name = name[4:]
            inverted = True
        return name, inverted

    def _invert(term: Tuple[str, bool]) -> Tuple[str, bool]:
        n, v = term
        return (n, not v)

    for channel, chan_cfg in cfg.items():
        skips = [
            skip
            for skip in skip_channels
            if skip["channel"] == channel
            or skip["channel"] in GROUP_DEFS
            and channel in GROUP_DEFS[skip["channel"]]
        ]
        if skips:
            print(f"Note: Skipping {channel}: {skips[0]['comment']}")
            continue
        reqs = channel_reqs[channel]
        if chan_cfg and chan_cfg["enabled"]:
            # Channels which are "on" must have all of their requirements met.
            for req in reqs:
                clause = CnfClause(
                    defn=frozenset({_eval(req)}),
                    comment=f"Required to enable {channel}",
                )
                clauses.add(clause)
        else:
            # Channels which are "off" must have at least one of their requirements unsatisfied.
            off_opts = frozenset([_invert(_eval(req)) for req in reqs])
            if off_opts:
                clause = CnfClause(
                    defn=off_opts, comment=f"Required to disable {channel}"
                )
                clauses.add(clause)
    return clauses


SettingsAssignment = FrozenSet[Tuple[str, bool]]


def display_cnf(cnf: CnfFormula) -> str:
    def display_clause(clause: CnfClause) -> str:
        return "({}) # {}".format(
            " ∨ ".join(
                [
                    literal if not inverted else "¬" + literal
                    for literal, inverted in clause.defn
                ]
            ),
            clause.comment,
        )

    return "\n∧ ".join(display_clause(clause) for clause in cnf)


def solve(clauses: CnfFormula) -> Set[SettingsAssignment]:
    """
    Find valid solutions to the conjunctive normal form formula given.
    """
    literals: Set[str] = set()
    for clause in clauses:
        for binding in clause.defn:
            n, _ = binding
            literals.add(n)

    # Generate all possible variable assignments. We track just the literals bound to "true".
    assignments = powerset(literals)

    # An assignment is satisfying if, when each literal is substituted for its bound value, the
    # formula reduces to True.
    def _is_sat(assignment: Sequence[str]) -> bool:
        def _reduce(clause: CnfClause) -> bool:
            # Note that the clause is a series of elements of the form (name, inverted). If the
            # second element is True, that means that the binding for the literal should be NOT-ed.
            # Notice that the truth table is symmetrical:
            #   T F < Binding
            # T F T
            # F T F
            # ^ Inverted
            # The operation is an XOR on the two variables.
            return any([inv != (n in assignment) for (n, inv) in clause.defn])

        return all([_reduce(clause) for clause in clauses])

    def _expand(assignment: Sequence[str]) -> FrozenSet[Tuple[str, bool]]:
        expansion = []
        for literal in literals:
            expansion.append((literal, literal in assignment))
        return frozenset(expansion)

    satisfying = [_expand(a) for a in assignments if _is_sat(a)]
    if not satisfying:
        # TODO Extract conflict kernels and display them here. Reading the formula raw is hard!
        raise SettingsConflictError(
            "Incompatible settings!\n"
            "There are items which must be both enabled and disabled at the same time.\n"
            f"CNF formula contains a conflict:\n{display_cnf(clauses)}"
        )

    return set(satisfying)


def create_patch_for_asset(
    asset_data: Mapping[str, Any], assignments: Set[SettingsAssignment]
) -> Tuple[Mapping[str, Any], Mapping[str, bool]]:

    literals = set()
    possible_patches = []
    for assignment in assignments:
        patch = {}
        for literal, value in assignment:
            literals.add(literal)
            if bool(lookup(literal, asset_data)) != value:
                patch[literal] = value
        possible_patches.append(patch)

    fieldset: Dict[str, Any] = {lit: lookup(lit, asset_data) for lit in literals}

    # Produce a minimal patch.
    min_patch = sorted(possible_patches, key=lambda x: len(x))[0]

    return fieldset, min_patch


def confirm_patch(
    asset: str,
    existing: Mapping[str, Any],
    patch: Mapping[str, bool],
    channel_reqs: Mapping[str, Set[str]],
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
        (
            bold("Channel (* = Mismatch)"),
            bold("State"),
            bold('Required TK settings (¬x means "not x")'),
        )
    ]
    for chan, chan_cfg in cfg.items():
        assert chan_cfg is not None

        def strip_not(s: str) -> str:
            if s.startswith("not "):
                return s[4:]
            return s

        needs_patch = any([strip_not(req) in patch for req in channel_reqs[chan]])

        def highlight(s: str) -> str:
            if needs_patch:
                return colored(s, MISMATCH_COLOR, attrs=["bold"])
            else:
                return s

        chan_name = highlight(chan + " *" if needs_patch else chan)
        state = "Enabled" if chan_cfg["enabled"] else "Disabled"

        settings = "n/a"

        def _fmt_not(s: str) -> str:
            if s.startswith("not "):
                return f"(¬{s[4:]})"
            return s

        reqs = ", ".join(
            {
                f"{highlight(_fmt_not(req) + '*') if strip_not(req) in patch else _fmt_not(req)}"
                for req in channel_reqs[chan]
            }
        )
        if chan_cfg["enabled"]:
            settings = f"All of {{{reqs}}} " + highlight("are True") if reqs else "n/a"
        else:
            settings = f"One of {{{reqs}}} " + highlight("is False") if reqs else "n/a"

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

    for (asset, kind, cfg) in find_asset_configs(args.environment, args.kind):
        print(f"\rChecking {asset}...           ", end="")
        settings_cnf = generate_settings_requirements(
            cfg, CHANNEL_REQS[kind], SKIP_CHANS.get(asset, [])
        )
        try:
            assignments = solve(settings_cnf)

            if args.check_only:
                continue  # We're just verifying that the settings are representable.

            asset_data = load_tk_asset(args.environment, asset, kind)
            existing, patch = create_patch_for_asset(asset_data, assignments)
            if patch:
                if confirm_patch(
                    asset, existing, patch, CHANNEL_REQS[kind], cfg, args.yes
                ):
                    if not args.dry_run:
                        patch_tk_asset(args.environment, asset, kind, patch)
                    else:
                        print("(Skipped for dry run)")
                else:
                    print("Canceled.")
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                print(colored(f"\nAsset {asset} not found in TK; skipping", attrs=["bold"]))
            else:
                clean_run = False
                print(colored(f"\nHTTP error while updating {asset}: {e}", "red", attrs=["bold"]))
                if args.fail_fast:
                    raise e
        except Exception as e:
            clean_run = False
            print(colored(f"\nError updating {asset}: {e}", "red", attrs=["bold"]))
            if args.fail_fast:
                raise e

    if not clean_run:
        exit(1)


if __name__ == "__main__":
    main()
