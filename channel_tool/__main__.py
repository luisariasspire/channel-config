#! /usr/bin/env python3

import argparse
import difflib
import itertools
import os
import sys
from copy import deepcopy
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Union

from termcolor import colored

from channel_tool.asset_config import (
    infer_asset_type,
    load_asset_config,
    locate_assets,
    write_asset_config,
)
from channel_tool.audit import AuditReport
from channel_tool.typedefs import ChannelDefinition, DefsFile, Environment
from channel_tool.util import (
    ENVS,
    TEMPLATE_FILE,
    confirm,
    dump_yaml_string,
    load_yaml_file,
    load_yaml_value,
)
from channel_tool.validation import (
    filter_properties,
    load_schema,
    validate_all,
    validate_one,
)

CONTACT_TYPE_DEFS: DefsFile = load_yaml_file("contact_type_defs.yaml")


class AlreadyExistsError(Exception):
    pass


class NoConfigurationError(Exception):
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


def is_list_or_dict(x: Any) -> bool:
    return isinstance(x, Sequence) or isinstance(x, dict)


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
            if k in md and is_list_or_dict(md[k]):
                md[k] = merge(md[k], v)
            else:
                md[k] = v
        return md


def remove(a: Any, b: Any) -> Optional[Any]:
    """Recursively remove from the first argument all elements from the second.

    The deletion proceeds depth-first in a recursive fashion, removing any "leaf" value which
    matches both its path and value between the two arguments.

    If deletion of "leaf" elements in a non-root structure leaves it empty, that structure will be
    deleted. Containers which are non-empty after their children are processed are left in place. If
    the root node has no children after processing it is returned as an empty collection.

    The order of elements in a sequence does not matter: if an element of the first sequence matches
    any element of the second it is removed. Children of a sequence are not processed recursively,
    rather, they are checked for equality as a unit. This is because when editing nested structures
    with the channel_tool it is almost always an error to remove sub-structure from elements in an
    array rather than removing the entire structure atomically.

    If both arguments are atoms -- neither sequences nor dictionaries -- they are compared for
    equality and None is returned if they match.
    """
    # For containers, first process recursively and filter out Nones returned by child nodes, then
    # if container is empty return None. Handle strings as atoms.
    if isinstance(a, Sequence) and not isinstance(a, str):
        assert isinstance(b, Sequence)
        retained = []
        for elt in a:
            # Only remove elements from sequences that are perfect matches, otherwise if we recurse
            # we might remove fields from an object that leave it in an invalid state. We almost
            # never want to do that; we want to remove the whole thing, but only if it's exactly the
            # item we were looking for.
            if not any([elt == filt for filt in b]):
                retained.append(elt)
        return retained
    elif isinstance(a, dict):
        assert isinstance(b, dict)
        m = deepcopy(a)
        for k in b.keys():
            if k not in m:
                continue

            filtered = remove(m[k], b[k])
            if filtered:
                m[k] = filtered
            else:
                del m[k]
        return m
    else:  # Primitives
        if a == b:
            return None
        else:
            return a


LTE = "<="
GTE = ">="
LT = "<"
GT = ">"
EQ = "=="
NEQ = "!="

comparator_to_lambda = {
    LTE: lambda curr_value, target_value: curr_value <= target_value,
    GTE: lambda curr_value, target_value: curr_value >= target_value,
    LT: lambda curr_value, target_value: curr_value < target_value,
    GT: lambda curr_value, target_value: curr_value > target_value,
    EQ: lambda curr_value, target_value: curr_value == target_value,
    NEQ: lambda curr_value, target_value: curr_value != target_value,
}

VALID_COMPARATORS = " ".join(comparator_to_lambda.keys())


def compile_predicates(str_predicate: str) -> Any:
    # Takes a single predicate in string form
    # "<field_name> <comparator> <target_value>"
    # and returns a function which runs the predicate on a config dictionary

    predicate = str_predicate.split(" ")

    field_name = predicate[0]
    comparator = predicate[1]

    try:
        target_value: Any = float(predicate[2])
    except ValueError:
        target_value = predicate[2]

    if comparator not in comparator_to_lambda:
        raise ValueError(
            f"Invalid comparator {comparator}. Valid options are: {VALID_COMPARATORS}"
        )

    comparator_func = comparator_to_lambda[comparator]

    def predicate_func(config: Any) -> Optional[Any]:
        return comparator_func(config[field_name], target_value)

    return predicate_func


def update(
    current_config: Any, config_updates: Any, comparison_functions: Any = None
) -> Optional[Any]:
    print(f"\n\n\n {comparison_functions} \n\n\n")

    f"""Update will default to updating all values in a list unless predicates are defined.
    In that case existing configs will be filtered before the update.

    All mandatory fields need to be passed in. If a mandatory field need not update, its value should
    be set to null. If a mandatory field is not given, an exception will be raised.
    Optional fields that need not update may be omitted or set to null.

    Multiple predicates may be passed in. Each predicate is supplied using an option of the form
    -p <field_name> <comparator> <value>
    for example
    -p min_elevation_deg >= 25 -p downlink_rate_kbps == 300

    Valid comparators are: {VALID_COMPARATORS}
    """
    if isinstance(current_config, Sequence):
        assert isinstance(config_updates, Sequence)

        if all(
            isinstance(n, dict) for n in itertools.chain(current_config, config_updates)
        ):
            config_update = config_updates[0]  # Max one update at a time
            current_config = list(current_config)

            for config in current_config:
                if comparison_functions:
                    if not all(
                        comparison_function(config)
                        for comparison_function in comparison_functions
                    ):
                        continue

                for field_name in config_update:
                    if field_name not in config:
                        continue

                    if config_update[field_name] == None:
                        continue

                    config[field_name] = update(
                        config[field_name],
                        config_update[field_name],
                        comparison_functions,
                    )

            return current_config

        return config_updates
    elif isinstance(current_config, dict):
        assert isinstance(config_updates, dict)

        for key in config_updates:
            if key in current_config and config_updates[key]:
                current_config[key] = update(current_config[key], config_updates[key])

        return current_config

    return config_updates


# TODO Stricter type for arguments


def modify(cdef: ChannelDefinition, args: Any) -> ChannelDefinition:
    """Apply modifications to a channel from argparse arguments."""
    new_cdef = deepcopy(cdef)
    vargs = vars(args)
    fields = schema_fields()

    def get_field_value(field: str) -> Any:
        if field in vargs and vargs[field] is not None:
            return vargs[field]
        arg = f"{field}_file"
        if arg in vargs and vargs[arg] is not None:
            return vargs[arg]
        return None

    for field in fields:
        val = get_field_value(field)
        if val is not None:
            if args.mode == "overwrite":
                new_cdef[field] = val  # type: ignore
            elif args.mode == "merge":
                new_cdef[field] = merge(cdef[field], val)  # type: ignore
            elif args.mode == "remove":
                new_cdef[field] = remove(cdef[field], val)  # type: ignore
            elif args.mode == "update":
                new_cdef[field] = update(  # type: ignore
                    cdef[field], val, args.predicate  # type: ignore
                )  # type: ignore
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


def delete_config(args: Any) -> None:
    def do_delete(
        asset: str, channel: str, existing: Optional[ChannelDefinition]
    ) -> None:
        if existing is None:
            if args.require_existing:
                msg = (
                    f"No configuration for {channel} on {asset}."
                )
                if not args.fail_fast:
                    warn(msg)
                    return None
                else:
                    raise NoConfigurationError(msg)
        return None

    apply_update(args.environment, args.assets, args.channels, do_delete, yes=args.yes)


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


def audit_configs(args: Any) -> None:
    sats = locate_assets(args.environment, args.satellites)
    gss = locate_assets(args.environment, args.ground_stations)
    for sat, gs in itertools.product(sats, gss):
        report = AuditReport(args.environment, sat, gs)
        if report.shared or not args.matches_only:
            print(report)


def normalize_configs(args: Any) -> None:
    for asset in locate_assets(args.environment, args.assets):
        config = load_asset_config(args.environment, asset)
        write_asset_config(args.environment, asset, config)


def find_template(channel: str) -> ChannelDefinition:
    if os.path.exists(TEMPLATE_FILE):
        templates: Dict[str, ChannelDefinition] = load_yaml_file(TEMPLATE_FILE)
        if channel in templates:
            return templates[channel]
        else:
            raise MissingTemplateError(f"Could not find template for {channel}")
    else:
        raise FileNotFoundError(f"Could not find file {TEMPLATE_FILE}")


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
                    validate_one(updated_chan, file=asset, key=channel)
                if updated_chan != existing_chan:
                    if yes or confirm_changes(
                        asset, channel, existing_chan, updated_chan
                    ):
                        if updated_chan is None:
                            try:
                                del asset_config[channel]
                                print(f"Deleted {channel} definition for {asset}.")
                            except KeyError:
                                pass
                        else:
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
    a = dump_yaml_string(existing).splitlines(keepends=True)
    b = dump_yaml_string(new).splitlines(keepends=True)
    lines = max(len(a), len(b))  # Show all context
    d = difflib.unified_diff(a, b, n=lines)
    cd = [color_diff_line(l) for l in d]
    return "".join(cd)


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


def channel_list(val: str) -> List[str]:
    templates: Dict[str, ChannelDefinition] = load_yaml_file(TEMPLATE_FILE)
    all_channels = list(templates.keys())

    if val.lower() == "all":
        return all_channels
    elif val.lower() in CONTACT_TYPE_DEFS["groups"]:
        group: List[str] = CONTACT_TYPE_DEFS["groups"][val.lower()]
        return group
    elif val.lower().startswith("contact"):
        return str_to_list(val)
    else:
        raise ValueError(f"Unrecognized channel alias '{val}'")

def add_process_flags(parser: Any) -> None:
    """Flags modulating the editing process."""
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

def add_delete_flags(parser: Any) -> None:
    """Flags for deleting channels."""
    parser.add_argument(
        "-r",
        "--require-existing",
        action="store_true",
        help="Raise an error whenever the channel to delete does not currently exist.",
    )

def add_editing_flags(parser: Any) -> None:
    """Add flags for each channel definition field. Used for editing and overrides."""
    # Meta
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
        choices=["overwrite", "merge", "remove", "update"],
        default="overwrite",
        help=("The editing mode to use for combining record sub-fields."),
    )
    parser.add_argument(
        "-p",
        "--predicate",
        type=compile_predicates,
        default=None,
        nargs=1,
        help=("Optional predicates to select configs. Only valid with --mode=update."),
    )
    # Fields
    parser.add_argument(
        "--directionality",
        type=str,
        choices=["Bidirectional", "SpaceToEarth", "EarthToSpace"],
        help="The channel direction.",
    )
    parser.add_argument(
        "--contact_type",
        type=str,
        help="The contact type to use when creating contact windows from this channel.",
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
        type=str_to_yaml_collection,
        help="A YAML block describing the ground station constraints.",
    )
    parser.add_argument(
        "--ground_station_constraints_file",
        type=file_to_yaml_collection,
        help="A YAML file describing the ground station constraints.",
    )
    parser.add_argument(
        "--satellite_constraints",
        type=str_to_yaml_collection,
        help="A YAML block describing the satellite constraints.",
    )
    parser.add_argument(
        "--satellite_constraints_file",
        type=file_to_yaml_collection,
        help="A YAML file describing the satellite constraints.",
    )
    link_profile_group = parser.add_mutually_exclusive_group()
    link_profile_group.add_argument(
        "--link_profile",
        type=str_to_yaml_list,
        help="A YAML block describing the link profile of this contact type.",
    )
    link_profile_group.add_argument(
        "--link_profile_file",
        type=file_to_yaml_list,
        help="A YAML file containing the link profile of this contact type.",
    )
    window_parameters_group = parser.add_mutually_exclusive_group()
    window_parameters_group.add_argument(
        "--window_parameters",
        type=str_to_yaml_map,
        help="A YAML block describing the window parameters to use when scheduling contacts.",
    )
    window_parameters_group.add_argument(
        "--window_parameters_file",
        type=file_to_yaml_map,
        help="A YAML file containing the window parameters to use when scheduling contacts.",
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
    prog="python -m channel_tool",
    description="A utility to help with managing channels.",
)
PARSER.add_argument("--debug", action="store_true", help="Run in debugging mode.")

SUBPARSERS = PARSER.add_subparsers()

ADD_PARSER = SUBPARSERS.add_parser(
    "add", help="Add a channel configuration from a template.", aliases=["a"]
)
ADD_PARSER.set_defaults(func=add_config)
add_process_flags(ADD_PARSER)
add_editing_flags(ADD_PARSER)
add_asset_flags(ADD_PARSER)

DELETE_PARSER = SUBPARSERS.add_parser(
    "delete", help="Delete a channel configuration.", aliases=["d"]
)
DELETE_PARSER.set_defaults(func=delete_config)
add_process_flags(DELETE_PARSER)
add_delete_flags(DELETE_PARSER)
add_asset_flags(DELETE_PARSER)

EDIT_PARSER = SUBPARSERS.add_parser(
    "edit", help="Modify an existing channel configuration.", aliases=["e"]
)
EDIT_PARSER.set_defaults(func=edit_config)
add_process_flags(EDIT_PARSER)
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
AUDIT_PARSER.add_argument(
    "--matches_only",
    action="store_true",
    help=("Only print asset pairs that contain valid channels."),
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
VALIDATE_PARSER.set_defaults(func=lambda _: validate_all())

if __name__ == "__main__":
    try:
        args = PARSER.parse_args()

        if "func" not in args:
            err("Missing positional argument, I do not know what to do")
            PARSER.print_help()
            sys.exit(1)

        try:
            args.func(args)
        except Exception as e:
            if args.debug:
                raise e
            err(f"Error: {e}")
            err("(Tip: Use the --debug flag to get a full stack trace.)")
            sys.exit(1)
    except argparse.ArgumentError as e:
        err(f"Error while parsing command line arguments: {e}")
        sys.exit(1)
