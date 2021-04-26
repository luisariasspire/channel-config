#! /usr/bin/env python3

import argparse
import difflib
import itertools
import os
import sys
from copy import deepcopy
from io import StringIO
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import jsonschema
import requests
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from tabulate import tabulate
from termcolor import colored

from typedefs import (
    AssetConfig,
    AssetKind,
    ChannelDefinition,
    DefsFile,
    Environment,
    GroundStationKind,
    SatelliteKind,
    TkGroundStation,
    TkSatellite,
)
from util import GS_DIR, SAT_DIR, confirm, tk_url

ENVS = ["staging", "production"]
SCHEMA_FILE = "schema.yaml"
GROUND_STATION: GroundStationKind = "groundstation"
SATELLITE: SatelliteKind = "satellite"


with open("contact_type_defs.yaml") as f:
    yaml = YAML()
    CONTACT_TYPE_DEFS: DefsFile = yaml.load(f)


class AlreadyExistsError(Exception):
    pass


class NoConfigurationError(Exception):
    pass


class ValidationError(Exception):
    pass


class MissingTemplateError(Exception):
    pass


def info(s: str) -> None:
    print(s)


def warn(s: str) -> None:
    print(colored(s, "yellow"))


def err(s: str) -> None:
    print(colored(s, "red"))


def schema_fields() -> Set[str]:
    """Extract a set of possible field names in the channel JSON schema."""

    def discover_keys(s: Union[Dict[str, Any], List[Dict[str, Any]], Any]) -> Set[str]:
        """Extract the transitive closure of map keys from a nested dictionary."""
        keys: Set[str] = set()
        if isinstance(s, str):
            pass
        elif isinstance(s, Sequence):
            for v in s:
                keys = keys.union(discover_keys(v))
        else:
            try:
                for k, v in s.items():
                    keys.add(k)
                    keys = keys.union(discover_keys(v))
            except AttributeError:
                pass
        return keys

    schema = load_schema()
    return discover_keys(schema)


ListOrDict = Union[Sequence[Any], Mapping[str, Any]]


def merge(a: ListOrDict, b: ListOrDict) -> ListOrDict:
    if isinstance(a, Sequence):
        assert isinstance(b, Sequence)
        # Remove duplicate entries. These may be dictionaries, which are unhashable, so we cannot
        # use a set here. Generally these lists will be quite small so even this inefficient
        # algorithm is performant enough.
        ml = []
        for x in itertools.chain(a, b):
            if x not in ml:
                ml.append(x)

        if len(ml) > 0 and isinstance(ml[0], str):
            # Special case for lists of strings: sort them
            ml = sorted(ml)
        assert isinstance(ml, Sequence)
        return ml
    else:
        assert isinstance(a, dict)
        assert isinstance(b, dict)
        md = deepcopy(a)
        for k, v in b.items():
            if k in md:
                md[k] = merge(md[k], v)
            else:
                md[k] = v
        return md


def remove(a: ListOrDict, b: ListOrDict) -> ListOrDict:
    if isinstance(a, Sequence):
        assert isinstance(b, Sequence)
        return [x for x in a if x not in b]
    else:
        assert isinstance(a, dict)
        assert isinstance(b, dict)
        m = deepcopy(a)
        for k in b.keys():
            del m[k]
        return m


# TODO Stricter type for arguments
def modify(cdef: ChannelDefinition, args: Any) -> ChannelDefinition:
    """Apply modifications to a channel from argparse arguments."""
    new_cdef = deepcopy(cdef)
    vargs = vars(args)
    fields = schema_fields()
    for field in fields:
        if field in vargs and vargs[field] is not None:
            if args.mode == "overwrite":
                new_cdef[field] = vargs[field]  # type: ignore
            elif args.mode == "merge":
                new_cdef[field] = merge(cdef[field], vargs[field])  # type: ignore
            elif args.mode == "remove":
                new_cdef[field] = remove(cdef[field], vargs[field])  # type: ignore
    if args.comment:
        new_cdef.yaml_set_start_comment(args.comment)  # type: ignore
    return new_cdef


def add_config(args: Any) -> None:
    def do_add(
        asset: str, channel: str, existing: Optional[ChannelDefinition]
    ) -> ChannelDefinition:
        if existing is None:
            template = find_template(channel)
            return modify(template, args)
        else:
            msg = (
                f"Configuration for {channel} already exists on {asset}.\n"
                f"(Tip: Use `channel_tool edit {asset} {channel}` to edit the configuration.)"
            )
            if not args.fail_fast:
                warn(msg)
                return existing
            else:
                raise AlreadyExistsError(msg)

    apply_update(args.environment, args.assets, args.channels, do_add, yes=args.yes)


def edit_config(args: Any) -> None:
    def do_edit(
        asset: str, channel: str, existing: Optional[ChannelDefinition]
    ) -> Optional[ChannelDefinition]:
        if existing is not None:
            return modify(existing, args)
        else:
            msg = (
                f"No configuration for {channel} on {asset}.\n"
                f"(Tip: Use `channel_tool add {asset} {channel}` to add one from a template.)"
            )
            if not args.fail_fast:
                warn(msg)
                return None
            else:
                raise NoConfigurationError(msg)

    apply_update(args.environment, args.assets, args.channels, do_edit, yes=args.yes)


TK_ASSET_CACHE: Dict[
    Tuple[str, str, Optional[str]], Union[TkGroundStation, TkSatellite]
] = {}


# TODO enum type for assets
def load_tk_asset(
    env: Environment, kind: AssetKind, name: Optional[str] = None
) -> Union[TkGroundStation, TkSatellite]:
    if (env, kind, name) not in TK_ASSET_CACHE:
        # TODO Load all of the assets to populate cache rather than fetching them one by one
        if name:
            suffix = f"/{name}"
        else:
            suffix = ""
        r = requests.get(tk_url(env) + kind + suffix)
        r.raise_for_status()
        val = r.json()
        TK_ASSET_CACHE[(env, kind, name)] = val
        return val  # type: ignore
    else:
        return TK_ASSET_CACHE[(env, kind, name)]


def channel_rejection_reason(
    satellite: TkSatellite,
    ground_station: TkGroundStation,
    sat_chan: Optional[ChannelDefinition],
    gs_chan: Optional[ChannelDefinition],
) -> Optional[str]:
    """Apply channel matching rules and return the reason for mismatch, if any."""
    if gs_chan is None:
        return "Channel not configured on ground station"

    if sat_chan is None:
        return "Channel not configured on satellite"

    if not sat_chan["legal"]:
        return "Channel marked illegal on satellite"

    if not gs_chan["legal"]:
        return "Channel marked illegal on ground station"

    if not sat_chan["enabled"]:
        return "Channel disabled on satellite"

    if not gs_chan["enabled"]:
        return "Channel disabled on ground station"

    sat_dir = sat_chan["directionality"]
    gs_dir = gs_chan["directionality"]
    if sat_dir != gs_dir:
        return f"Directionality mismatch ({sat_dir} vs {gs_dir})"

    sat_countries = sat_chan["allowed_license_countries"]
    gs_countries = gs_chan["allowed_license_countries"]

    def normalize(country: str) -> str:
        return country[:2]

    sat_country = normalize(satellite["license_country"])
    gs_country = ground_station["license_country"]

    if sat_country not in gs_countries:
        return f"Satellite license country {sat_country} not in set {gs_countries}"

    if gs_country not in sat_countries:
        return f"Ground station license country {gs_country} not in set {sat_countries}"

    return None


def compare_channels(
    sat_config: AssetConfig,
    gs_config: AssetConfig,
    satellite: TkSatellite,
    ground_station: TkGroundStation,
) -> Tuple[List[Tuple[str, Optional[str]]], List[Tuple[str, Optional[str]]]]:
    """Compare the configured channels for the given satellite and ground station."""
    shared: List[Tuple[str, Optional[str]]] = []
    mismatched: List[Tuple[str, Optional[str]]] = []

    channels = set(sat_config.keys()).union(set(gs_config.keys()))
    for chan in channels:
        sat_chan = sat_config.get(chan)
        gs_chan = gs_config.get(chan)
        reason = channel_rejection_reason(satellite, ground_station, sat_chan, gs_chan)
        if reason:
            mismatched.append((chan, reason))
        else:
            if (
                sat_chan is not None
                and sat_chan.get("satellite_constraints") is not None
            ):
                shared.append((chan, "Note: Subject to satellite constraints"))
            else:
                shared.append((chan, None))
    shared = sorted(shared)
    mismatched = sorted(mismatched)
    return (shared, mismatched)


def audit_config(env: Environment, sat: str, gs: str) -> None:
    """Compute and display a report of the channel (mis)matches between assets."""
    sat_config = load_asset_config(env, sat)
    gs_config = load_asset_config(env, gs)
    satellite = load_tk_asset(env, SATELLITE, sat)
    ground_station = load_tk_asset(env, GROUND_STATION, gs)

    shared, mismatched = compare_channels(
        sat_config, gs_config, satellite, ground_station
    )

    header = f"Audit summary for {sat} -> {gs}"
    print(header)
    print("=" * len(header), end="\n\n")

    print("Valid Channels")
    if shared:
        print(tabulate(shared))
    else:
        print(colored("(No channels passed licensing rules)", "magenta"))
    print()

    print("Rejected Channels")
    print(tabulate(mismatched))
    print()


def audit_configs(args: Any) -> None:
    sats = locate_assets(args.environment, args.satellites)
    gss = locate_assets(args.environment, args.ground_stations)
    for sat, gs in itertools.product(sats, gss):
        audit_config(args.environment, sat, gs)


def validate_all(args: Any) -> None:
    for asset_type in [GROUND_STATION, SATELLITE]:
        print(f"Validating {asset_type} templates...")
        validate_file(
            "templates.yaml",
            inspect_keys=True,
            preprocess=lambda x: filter_properties(asset_type, x),
        )
        print(colored("PASS", "green"))

    for env in ENVS:
        print(f"Validating {env} satellites...")
        sat_dir = os.path.join(env, SAT_DIR)
        all_sats = os.listdir(sat_dir)
        for sf in all_sats:
            print(f"{sf}... ", end="")
            validate_file(os.path.join(sat_dir, sf))
            print(colored("PASS", "green"))

        print(f"Validating {env} ground stations...")
        gs_dir = os.path.join(env, GS_DIR)
        all_stations = os.listdir(gs_dir)
        for gsf in all_stations:
            print(f"{gsf}... ", end="")
            validate_file(os.path.join(gs_dir, gsf))
            print(colored("PASS", "green"))

    print("All passed!")


def validate_file(
    cf: str,
    inspect_keys: bool = True,
    preprocess: Optional[Callable[[ChannelDefinition], ChannelDefinition]] = None,
) -> None:
    with open(cf) as f:
        yaml = YAML()
        config = yaml.load(f)
        if inspect_keys:
            for key in config:
                try:
                    c = config[key]
                    if preprocess:
                        c = preprocess(c)
                    validate_one(c)
                except Exception as e:
                    raise ValidationError(f"Failed to validate {cf}#{key}: {e}")
        else:
            try:
                c = config
                if preprocess:
                    c = preprocess(c)
                validate_one(config)
            except Exception as e:
                raise ValidationError(f"Failed to validate {cf}: {e}")


def validate_one(config: ChannelDefinition) -> None:
    schema = load_schema()
    jsonschema.validate(config, schema)


# Memoize the JSON Schema definition.
loaded_schema = None


def load_schema() -> Any:
    global loaded_schema
    if not loaded_schema:
        yaml = YAML()
        with open(SCHEMA_FILE) as f:
            # File has "schema" and "definitions" as top-level fields.
            loaded_schema = yaml.load(f)["schema"]
    return loaded_schema


def normalize_configs(args: Any) -> None:
    for asset in locate_assets(args.environment, args.assets):
        config = load_asset_config(args.environment, asset)
        write_asset_config(args.environment, asset, config)


def normalize_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a configuration file by removing anchors and sorting keys."""
    new_config: Dict[str, Any] = CommentedMap()
    for k in sorted(cfg):
        new_config[k] = deepcopy(cfg[k])
    return new_config


def find_template(channel: str) -> ChannelDefinition:
    template_file = "templates.yaml"
    if os.path.exists(template_file):
        with open(template_file) as f:
            yaml = YAML()
            templates: Dict[str, ChannelDefinition] = yaml.load(f)
            if channel in templates:
                return templates[channel]
            else:
                raise MissingTemplateError(f"Could not find template for {channel}")
    else:
        raise FileNotFoundError(f"Could not find file {template_file}")


def locate_assets(env: Environment, assets: Union[str, List[str]]) -> List[str]:
    def name(p: str) -> str:
        return os.path.splitext(os.path.basename(p))[0]

    if isinstance(assets, list):
        return assets
    elif assets == "all_gs":
        return sorted([name(p) for p in os.listdir(os.path.join(env, GS_DIR))])
    elif assets == "all_sat":
        return sorted([name(p) for p in os.listdir(os.path.join(env, SAT_DIR))])
    elif assets == "all":
        vs = locate_assets(env, "all_gs")
        vs.extend(locate_assets(env, "all_sat"))
        return vs
    else:
        return assets.split(",")


def filter_properties(asset_type: str, chan: ChannelDefinition) -> ChannelDefinition:
    """Filter the channel configuration properties based on the asset type."""
    if chan:
        if asset_type != GROUND_STATION and "ground_station_constraints" in chan:
            del chan["ground_station_constraints"]
        if asset_type != SATELLITE and "satellite_constraints" in chan:
            del chan["satellite_constraints"]
    return chan


def apply_update(
    env: Environment,
    assets: List[str],
    channels: List[str],
    tfm: Callable[[str, str, Optional[ChannelDefinition]], Optional[ChannelDefinition]],
    yes: bool = False,
) -> None:
    for asset in locate_assets(env, assets):
        asset_config = load_asset_config(env, asset)
        for channel in channels:
            existing_chan = asset_config.get(channel)
            try:
                updated_chan = tfm(asset, channel, existing_chan)
                if updated_chan is not None:
                    asset_type = infer_asset_type(asset)
                    updated_chan = filter_properties(asset_type, updated_chan)
                    validate_one(updated_chan)
                if updated_chan != existing_chan:
                    if yes or confirm_changes(
                        asset, channel, existing_chan, updated_chan
                    ):
                        # Deepcopy here to try to avoid YAML being too smart and combining
                        # structures. It makes diffs hard to read.
                        asset_config[channel] = deepcopy(updated_chan)
                        print(f"Updated {channel} definition for {asset}.")
                else:
                    print(colored(f"No changes for {channel} on {asset}.", "magenta"))
            except AlreadyExistsError as e:
                err(f"Error: {e}")
        write_asset_config(env, asset, asset_config)


def confirm_changes(
    asset: str,
    channel: str,
    existing: Optional[ChannelDefinition],
    new: Optional[ChannelDefinition],
) -> bool:
    ch = colored(channel, attrs=["bold"])
    at = colored(asset, attrs=["bold"])
    print(f"Changing {ch} on {at}. Diff:")
    print(format_diff(existing, new))
    if confirm("Update asset configuration?"):
        return True
    else:
        warn("Canceled.")
        return False


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
    a = dumps(existing).splitlines(keepends=True)
    b = dumps(new).splitlines(keepends=True)
    lines = max(len(a), len(b))  # Show all context
    d = difflib.unified_diff(a, b, n=lines)
    cd = [color_diff_line(l) for l in d]
    return "".join(cd)


def dumps(obj: Optional[Mapping[str, Any]]) -> str:
    with StringIO() as stream:
        yaml = YAML()
        yaml.dump(obj, stream)
        return stream.getvalue()


CONFIG_CACHE: Dict[Tuple[str, str], AssetConfig] = {}


def load_asset_config(env: Environment, asset: str) -> AssetConfig:
    def do_load() -> AssetConfig:
        config_file = infer_config_file(env, asset)
        if not os.path.exists(config_file):
            return {}
        with open(config_file, mode="r") as f:
            yaml = YAML()
            config: Optional[AssetConfig] = yaml.load(f)
            if config:
                return config
            else:
                return {}

    if not (env, asset) in CONFIG_CACHE:
        config = do_load()
        CONFIG_CACHE[(env, asset)] = config
        return config
    else:
        return CONFIG_CACHE[(env, asset)]


def write_asset_config(env: Environment, asset: str, asset_config: AssetConfig) -> None:
    config_file = infer_config_file(env, asset)
    if asset_config:
        asset_config = normalize_config(asset_config)
        with open(config_file, mode="w+") as f:
            yaml = YAML()
            yaml.dump(asset_config, f)
    elif os.path.exists(config_file):
        os.remove(config_file)


def infer_asset_type(asset: str) -> str:
    if asset.endswith("gs"):
        return GROUND_STATION
    else:
        return SATELLITE


def infer_config_file(env: Environment, asset: str) -> str:
    asset_type = infer_asset_type(asset)
    if asset_type == GROUND_STATION:
        # Assumed to be a ground station.
        return os.path.join(env, GS_DIR, asset + ".yaml")
    elif asset_type == SATELLITE:
        # Assumed to be a satellite.
        return os.path.join(env, SAT_DIR, asset + ".yaml")
    else:
        raise ValueError(f"Unexpected asset type {asset_type}")


def str_to_yaml(val: str) -> Mapping[str, Any]:
    yaml = YAML()
    v = yaml.load(val)
    assert isinstance(v, dict), "Expected YAML key-value mapping"
    return v


def str_to_list(values: str) -> List[str]:
    return values.split(",")


def str_to_bool(val: str) -> bool:
    if val.lower() in ["y", "yes", "true", "1"]:
        return True
    if val.lower() in ["n", "no", "false", "0"]:
        return False
    raise ValueError(f"Unrecognized input '{val}'")


def channel_list(val: str) -> List[str]:
    yaml = YAML()
    with open("templates.yaml", "r") as f:
        templates: Dict[str, ChannelDefinition] = yaml.load(f)
        all_channels = list(templates.keys())

    if val.lower() == "all":
        return all_channels
    elif val.lower() in CONTACT_TYPE_DEFS["groups"]:
        return CONTACT_TYPE_DEFS["groups"][val.lower()]
    elif val.lower().startswith("contact"):
        return str_to_list(val)
    else:
        raise ValueError(f"Unrecognized channel alias '{val}'")


def add_editing_flags(parser: Any) -> None:
    """Add flags for each channel definition field. Used for editing and overrides."""
    # Meta
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation dialogs and make all edits.",
    )
    parser.add_argument(
        "-f",
        "--fail-fast",
        action="store_true",
        help="Do not continue with further edits after errors.",
    )
    parser.add_argument(
        "-c",
        "--comment",
        type=str,
        help="Optional comment to attach to the channel definition in the YAML file.",
    )
    parser.add_argument(
        "-m",
        "--mode",
        type=str,
        choices=["overwrite", "merge", "remove"],
        default="overwrite",
        help=("The editing mode to use for combining record sub-fields."),
    )

    # Fields
    parser.add_argument(
        "--directionality",
        type=str,
        choices=["Bidirectional", "SpaceToEarth", "EarthToSpace"],
        help="The channel direction.",
    )
    parser.add_argument(
        "--allowed_license_countries",
        type=str_to_list,
        help="The license countries which this channel can be used with as a comma separated list.",
    )
    parser.add_argument(
        "--enabled", type=str_to_bool, help="Whether the channel is enabled for use."
    )
    parser.add_argument(
        "--legal",
        type=str_to_bool,
        help="Whether the channel is licensed for legal use.",
    )
    parser.add_argument(
        "--contact_overhead_time",
        type=str,
        help=(
            "Overhead (non-download) time to account for when using this contact type,"
            " in 'humantime' format."
        ),
    )
    parser.add_argument(
        "--ground_station_constraints",
        type=str_to_yaml,
        help="A YAML block describing the ground station constraints.",
    )
    parser.add_argument(
        "--satellite_constraints",
        type=str_to_yaml,
        help="A YAML block describing the satellite constraints.",
    )
    parser.add_argument(
        "--link_profile",
        type=str_to_yaml,
        help="A YAML block describing the link profile of this contact type.",
    )


def add_env_flag(parser: Any) -> None:
    parser.add_argument(
        "environment",
        type=str,
        choices=ENVS,
        help=("Which environment to configure."),
    )


def add_asset_flag(parser: Any) -> None:
    parser.add_argument(
        "assets",
        type=str,
        help=(
            "The satellites or ground stations to act on. "
            "Can be a comma separated list of asset IDs, 'all_gs', 'all_sat', or 'all'."
        ),
    )


def add_channel_flag(parser: Any) -> None:
    aliases = ", ".join([f"'{g}'" for g in CONTACT_TYPE_DEFS["groups"].keys()])
    parser.add_argument(
        "channels",
        type=channel_list,
        help=(
            "The channels to act on as a comma separated list. "
            f"Also supports the following aliases: {aliases} or 'all'."
        ),
    )


def add_asset_flags(parser: Any) -> None:
    add_env_flag(parser)
    add_asset_flag(parser)
    add_channel_flag(parser)


PARSER = argparse.ArgumentParser(
    description="A utility to help with managing channels."
)
PARSER.add_argument("--debug", action="store_true", help="Run in debugging mode.")

SUBPARSERS = PARSER.add_subparsers()

ADD_PARSER = SUBPARSERS.add_parser(
    "add", help="Add a channel configuration from a template.", aliases=["a"]
)
ADD_PARSER.set_defaults(func=add_config)
add_editing_flags(ADD_PARSER)
add_asset_flags(ADD_PARSER)

EDIT_PARSER = SUBPARSERS.add_parser(
    "edit", help="Modify an existing channel configuration.", aliases=["e"]
)
EDIT_PARSER.set_defaults(func=edit_config)
add_editing_flags(EDIT_PARSER)
add_asset_flags(EDIT_PARSER)

AUDIT_PARSER = SUBPARSERS.add_parser(
    "audit", help="Audit a satellite/ground station pair to find usable channels."
)
AUDIT_PARSER.set_defaults(func=audit_configs)

add_env_flag(AUDIT_PARSER)
AUDIT_PARSER.add_argument(
    "satellites",
    type=str,
    help=("The satellites to audit."),
)
AUDIT_PARSER.add_argument(
    "ground_stations",
    type=str,
    help=("The ground stations to audit."),
)

NORMALIZE_PARSER = SUBPARSERS.add_parser(
    "normalize", help="Convert configuration to a normalized format."
)
NORMALIZE_PARSER.set_defaults(func=normalize_configs)
add_env_flag(NORMALIZE_PARSER)
add_asset_flag(NORMALIZE_PARSER)

VALIDATE_PARSER = SUBPARSERS.add_parser(
    "validate", help="Validate all templates and extant configurations."
)
VALIDATE_PARSER.set_defaults(func=validate_all)


if __name__ == "__main__":
    try:
        args = PARSER.parse_args()
        try:
            args.func(args)
        except Exception as e:
            if args.debug:
                raise e
            err(f"Error: {e}")
            err("(Tip: Use the --debug flag to get a full stack trace.)")
            sys.exit(1)
    except Exception as e:
        err(f"Error while parsing command line arguments: {e}")
        sys.exit(1)
