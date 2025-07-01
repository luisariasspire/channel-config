#! /usr/bin/env python3

import argparse
import itertools
import re
import sys
from copy import deepcopy
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Union

from deepdiff import DeepDiff
from termcolor import colored

import channel_tool.database as db
from channel_tool.asset_config import (
    asset_config_to_string,
    infer_asset_type,
    infer_config_file,
    load_asset_config,
    locate_assets,
    write_asset_config,
)
from channel_tool.audit import AuditReport
from channel_tool.auto_update_utils import create_config_updates, read_history
from channel_tool.duplicate import DuplicateError, duplicate, gen_channel_id
from channel_tool.pls_tool import pls_long, pls_lookup, pls_short
from channel_tool.typedefs import ChannelDefinition, DefsFile, Environment
from channel_tool.util import (
    ENVS,
    GROUND_STATION,
    GS_TEMPLATE_FILE,
    SAT_TEMPLATE_FILE,
    confirm,
    dump_yaml_file,
    err,
    file_to_yaml_collection,
    file_to_yaml_list,
    file_to_yaml_map,
    find_template,
    format_diff,
    load_yaml_file,
    str_to_bool,
    str_to_list,
    str_to_yaml_collection,
    str_to_yaml_list,
    str_to_yaml_map,
    warn,
)
from channel_tool.validation import (
    check_element_conforms_to_schema,
    load_gs_schema,
    load_sat_schema,
    validate_all,
)

CONTACT_TYPE_DEFS: DefsFile = load_yaml_file("contact_type_defs.yaml")


class AlreadyExistsError(Exception):
    pass


class NoConfigurationError(Exception):
    pass


class IncorrectInput(Exception):
    pass


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

    sat_schema = load_sat_schema()
    sat_keys = discover_keys(sat_schema)
    gs_schema = load_gs_schema()
    gs_keys = discover_keys(gs_schema)
    return sat_keys.union(gs_keys)


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


def compile_predicate(str_predicate: str) -> Any:
    """
    Takes a single predicate in string form
    "<field_name> <comparator> <target_value>"
    and returns a function which runs the predicate on a config dictionary
    """

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
    """Update will default to updating all values in a list unless predicates are defined.
    In that case existing configs will be filtered before the update.

    Only the fields to be updated are mandatory. The rest may be set to None or be omitted
    completely.

    Multiple predicates may be passed in. Each predicate is supplied using an option of the form
    -p <field_name> <comparator> <value>
    for example
    -p min_elevation_deg >= 25 -p downlink_rate_kbps == 300
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

                    if config_update[field_name] is None:
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
            # Mode is an arg below, but it's also a schema key. We should except this from this functionality.
            if field != "mode":
                return vargs[field]
        arg = f"{field}_file"
        if arg in vargs and vargs[arg] is not None:
            return vargs[arg]
        return None

    for field in fields:
        try:
            val = get_field_value(field)
            if val is not None:
                if args.mode == "overwrite":
                    new_cdef[field] = val  # type: ignore
                elif args.mode == "merge":
                    new_cdef[field] = merge(cdef.get(field, {}), val)  # type: ignore
                elif args.mode == "remove":
                    new_cdef[field] = remove(cdef.get(field, {}), val)  # type: ignore
                elif args.mode == "update":
                    new_cdef[field] = update(  # type: ignore
                        # type: ignore
                        cdef.get(field, {}),
                        val,
                        args.predicate,
                    )  # type: ignore
        except Exception as e:
            raise Exception(f"Failed to '{args.mode}' field '{field}'") from e

    if args.comment:
        new_cdef.yaml_set_start_comment(args.comment)  # type: ignore
    return new_cdef


def auto_update(asset: str, cdef: ChannelDefinition, args: Any) -> ChannelDefinition:
    """Create configuration updates and predicates. Then make the updates"""

    new_cdef = deepcopy(cdef)
    field = args.parameter

    config_updates = create_config_updates(args, args.history)
    # filter out low elevation UHF link profiles
    predicates = [compile_predicate("downlink_rate_kbps > 20")]
    new_cdef[field] = update(cdef[field], config_updates, predicates)  # type: ignore

    if args.comment:
        new_cdef.yaml_set_start_comment(args.comment)  # type: ignore

    return new_cdef


def add_config(args: Any) -> None:
    def do_add(
        asset: str, channel: str, existing: Optional[ChannelDefinition]
    ) -> ChannelDefinition:
        if existing is None:
            asset_type = infer_asset_type(asset)
            template = find_template(asset_type, channel)
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
                msg = f"No configuration for {channel} on {asset}."
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


def auto_update_config(args: Any) -> None:
    def do_auto_update(
        asset: str, channel: str, existing: Optional[ChannelDefinition]
    ) -> Optional[ChannelDefinition]:
        if existing is not None:
            return auto_update(asset, existing, args)
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

    history = read_history(args.data_column, args.source_file, args.conversion_factor)

    for channel_id, hist in history.items():
        args.history = hist
        apply_update(
            args.environment, args.assets, [channel_id], do_auto_update, yes=args.yes
        )


def duplicate_config(args: Any) -> None:
    def do_duplicate(
        asset: str, channel: str, existing: Optional[ChannelDefinition]
    ) -> Optional[ChannelDefinition]:
        if not existing:
            raise Exception("Duplicate requires an existing channel!")

        # This is going to run many times so let's avoid file i/o when we can
        class_annos = existing.get("classification_annotations") or find_template(
            GROUND_STATION, channel
        ).get("classification_annotations")

        return duplicate(args, existing, class_annos)

    # Find the first channel in `args.channels` that exists in the asset config
    # for each asset and duplicate that.
    for asset in args.assets.split(","):
        asset_config = load_asset_config(args.environment, asset)
        existing_channel = None
        for channel in args.channels:
            if channel in asset_config:
                existing_channel = channel
                break

        if not existing_channel:
            warn(f"None of the channels in {args.channels} exist in {asset}.")
            return None

        print(f"Duplicating {existing_channel} within {asset}")

        apply_update(
            args.environment,
            [asset],
            [existing_channel],
            do_duplicate,
            yes=args.yes,
            new_channel=True,
            args=args,
        )


def audit_configs(args: Any) -> None:
    sats = locate_assets(args.environment, args.satellites)
    gss = locate_assets(args.environment, args.ground_stations)
    for sat, gs in itertools.product(sats, gss):
        report = AuditReport(args.environment, sat, gs)
        if report.shared or not args.matches_only:
            print(report)


def query_configs(args: Any) -> None:
    print(f"asset,channel,{args.field}")
    for asset in locate_assets(args.environment, args.assets):
        asset_config = load_asset_config(args.environment, asset)
        for channel in args.channels:
            existing_channel = asset_config.get(channel)
            if not existing_channel:
                continue
            value = existing_channel.get(args.field, None)
            print(f"{asset},{channel},{value}")


def diff_configs(args: Any) -> None:
    assets_dict = {}
    for env in args.environment.split(","):
        for asset in locate_assets(env, args.assets):
            asset_config = load_asset_config(env, asset)
            # assets_dict[env] = {asset: asset_config}
            assets_dict[f"{env}-{asset}"] = asset_config

    for permutation in itertools.combinations(assets_dict.keys(), 2):
        diff = DeepDiff(
            assets_dict[permutation[0]],
            assets_dict[permutation[1]],
            ignore_order=True,
            verbose_level=args.verbose,
        )
        out = f"Difference between {permutation[0]} and {permutation[1]}"
        sep = "=" * len(out)
        out = "\n" + out + "\n" + sep + "\n"
        print(out)
        if diff:  # if diff is not empty
            print(f"{diff.pretty()}\n")
        else:
            print("None\n")


def normalize_configs(args: Any) -> None:
    for asset in locate_assets(args.environment, args.assets):
        config = load_asset_config(args.environment, asset)
        write_asset_config(args.environment, asset, config)


def format_configs(args: Any) -> None:
    pass_check = True
    gs_templates = load_yaml_file(GS_TEMPLATE_FILE)
    pass_check = format_asset(args, gs_templates, GS_TEMPLATE_FILE) and pass_check
    sat_templates = load_yaml_file(SAT_TEMPLATE_FILE)
    pass_check = format_asset(args, sat_templates, SAT_TEMPLATE_FILE) and pass_check
    for env in ENVS:
        all_assets = locate_assets(env, "all_gs")
        all_assets.extend(locate_assets(env, "all_sat"))
        for asset in sorted(all_assets):
            path = infer_config_file(env, asset)
            config = load_asset_config(env, asset)
            pass_check = format_asset(args, config, path) and pass_check
    if args.check and not pass_check:
        print(
            "Use the channel_tool 'format' or 'normalize' commands to correct non-standard formatting"
        )
        exit(1)


def duplicate_template(new_channel_id: str, old_channel_id: str, asset: str) -> None:
    file = (
        GS_TEMPLATE_FILE
        if infer_asset_type(asset) == "groundstation"
        else SAT_TEMPLATE_FILE
    )

    templates = load_yaml_file(file)

    if new_channel_id in templates:
        warn(f"{new_channel_id} already exists in {file}. No-op.")
        return

    old_template = templates[old_channel_id]
    template_class_annos = (
        old_template.get("classification_annotations")
        or find_template(GROUND_STATION, old_channel_id)["classification_annotations"]
    )
    new_template = duplicate(args, old_template, template_class_annos)

    templates[new_channel_id] = deepcopy(new_template)
    dump_yaml_file(templates, file)

    print(f"Added {new_channel_id} to {file}.")


def rename_channel(args: Any) -> None:
    any_updates = False
    current_name = args.current_name
    new_name = args.new_name
    gs_templates = load_yaml_file(GS_TEMPLATE_FILE)
    any_updates |= rename_channel_in_configs(
        gs_templates, GS_TEMPLATE_FILE, current_name, new_name
    )
    sat_templates = load_yaml_file(SAT_TEMPLATE_FILE)
    any_updates |= rename_channel_in_configs(
        sat_templates, SAT_TEMPLATE_FILE, current_name, new_name
    )
    for env in ENVS:
        all_assets = locate_assets(env, "all_gs")
        all_assets.extend(locate_assets(env, "all_sat"))
        for asset in all_assets:
            path = infer_config_file(env, asset)
            configs = load_asset_config(env, asset)
            any_updates |= rename_channel_in_configs(
                configs, path, current_name, new_name
            )
    if not any_updates:
        print(f"No channel {current_name} found in any config or template")


def rename_channel_in_configs(
    configs: Any, path: str, current_name: str, new_name: str
) -> bool:
    config = configs.pop(current_name, None)
    if config:
        configs[new_name] = config
        configs_string = asset_config_to_string(configs)
        with open(path, "w") as f:
            f.write(configs_string)
        print(f"Renamed channel {current_name} to {new_name} in {path}")
        return True
    return False


def format_asset(args: Any, config: Any, path: str) -> bool:
    with open(path) as f:
        string_before = f.read()
    string_after = asset_config_to_string(config)
    if string_before == string_after:
        if not args.check:
            print(f"Formatting {path}: no update required")
        return True
    else:
        if args.check:
            print(f"Formatting {path}: file would be updated")
        else:
            print(f"Formatting {path}: updated")
            with open(path, "w") as f:
                f.write(string_after)
        return False


def apply_update(
    env: Environment,
    assets: List[str],
    channels: List[str],
    tfm: Callable[[str, str, Optional[ChannelDefinition]], Optional[ChannelDefinition]],
    yes: bool = False,
    new_channel: Optional[bool] = False,
    args: Optional[Any] = None,
) -> None:
    for asset in locate_assets(env, assets):
        asset_config = load_asset_config(env, asset)
        for channel in channels:
            existing_chan = asset_config.get(channel)
            try:
                updated_chan = tfm(asset, channel, existing_chan)

                if updated_chan is not None:
                    # new_channel is specified when we operated on an existing
                    # channel but want to save our changes under a new id. We
                    # need to update existing_chan so that the diff is correct
                    # and channel so that we use the new channel id from here
                    # on.
                    if new_channel:
                        # This is going to run many times so let's avoid file i/o when we can
                        class_annos = updated_chan.get(
                            "classification_annotations"
                        ) or find_template(GROUND_STATION, channel).get(
                            "classification_annotations"
                        )
                        new_channel_id = gen_channel_id(args, class_annos)
                        existing_chan = None
                        old_channel_id = channel
                        channel = new_channel_id

                    asset_type = infer_asset_type(asset)
                    check_element_conforms_to_schema(
                        asset_type, updated_chan, file=asset, key=channel
                    )

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
                            updated_chan = deepcopy(updated_chan)
                            asset_config[channel] = updated_chan
                            print(f"Updated {channel} definition for {asset}.")

                            # If we're creating a new channel, also add it to
                            # the templates
                            if new_channel:
                                duplicate_template(channel, old_channel_id, asset)
                else:
                    print(colored(f"No changes for {channel} on {asset}.", "magenta"))
            except AlreadyExistsError as e:
                err(f"Error: {e}")
            except DuplicateError as e:
                err(f"Error: {e}")
            except Exception as e:
                err(
                    f"Unhandled exception with asset {asset} and channel {channel} : {e}"
                )
                raise
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


def channel_list(val: str) -> List[str]:
    sat_templates: Dict[str, ChannelDefinition] = load_yaml_file(SAT_TEMPLATE_FILE)
    gs_templates: Dict[str, ChannelDefinition] = load_yaml_file(GS_TEMPLATE_FILE)
    all_channels = list(set(sat_templates.keys()).union(set(gs_templates.keys())))
    gs_schema = load_gs_schema()
    classification_annotations_schema: dict[str, Any] = gs_schema["properties"][
        "classification_annotations"
    ]["properties"]

    # Matches a string if it contains classification annotation keys
    # Used to figure out if the input is a predicate
    classification_annotations_keys = list(classification_annotations_schema.keys())
    regex = re.compile(f".*(?=({'|'.join(classification_annotations_keys)}))")

    if val.lower() == "all":
        return all_channels
    elif val.lower() in CONTACT_TYPE_DEFS["groups"]:
        group_predicate = CONTACT_TYPE_DEFS["groups"][val.lower()]
        return channels_from_predicate(
            group_predicate, gs_templates, classification_annotations_schema
        )
    elif regex.match(val):
        return channels_from_predicate(
            val, gs_templates, classification_annotations_schema
        )
    else:
        channels: List[str] = str_to_list(val)
        return channels


def channels_from_predicate(
    val: str,
    gs_templates: Dict[str, ChannelDefinition],
    classification_annotations_schema: dict[str, Any],
) -> List[str]:
    # Don't need the giant stack trace if this fails. Just give us the error message.
    sys.tracebacklimit = -1
    # Check that we can evaluate the predicate against the classification
    # annotations schema which means it doesn't contain any invalid keys
    eval(val, classification_annotations_schema)
    # Reset back to the default
    # https://docs.python.org/3/library/sys.html#sys.tracebacklimit
    sys.tracebacklimit = 1000

    def evaluate(annos: Dict[str, Any]) -> Any:
        # Add missing keys to the annotations and set them to None
        # This allows us to run predicates that contain keys that doesn't
        # exist on a channel. `eval` is short circuiting and treats non-existent
        # keys as exceptions. So this allows us to run predicates like:
        # (not space_ground_sband_mid_freq_mhz or space_ground_sband_mid_freq_mhz == 2022.5)
        # which would otherwise raise `NameError` for XBand channels.
        for key in classification_annotations_schema.keys() - annos.keys():
            annos[key] = None

        return eval(val, annos)

    return [
        id
        for id, cdef in gs_templates.items()
        if evaluate(cdef["classification_annotations"])
    ]


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
    parser.add_argument(
        "-c",
        "--comment",
        type=str,
        help="Optional comment to attach to the channel definition in the YAML file.",
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
        type=compile_predicate,
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
    dynamic_window_parameters_group = parser.add_mutually_exclusive_group()
    dynamic_window_parameters_group.add_argument(
        "--dynamic_window_parameters",
        type=str_to_yaml_map,
        help="A YAML block describing the dynamic window parameters config to use when scheduling contacts.",
    )
    dynamic_window_parameters_group.add_argument(
        "--dynamic_window_parameters_file",
        type=file_to_yaml_map,
        help="A YAML file containing the dynamic window parameters config to use when scheduling contacts.",
    )
    classification_annotations_group = parser.add_mutually_exclusive_group()
    classification_annotations_group.add_argument(
        "--classification_annotations",
        type=str_to_yaml_map,
        help="A YAML block describing the classification annotations to use when scheduling contacts.",
    )
    classification_annotations_group.add_argument(
        "--classification_annotations_file",
        type=file_to_yaml_map,
        help="A YAML file containing the  classification annotations to use when scheduling contacts.",
    )
    additional_provider_config = parser.add_mutually_exclusive_group()
    additional_provider_config.add_argument(
        "--additional_provider_config",
        type=str_to_yaml_map,
        help="A YAML block describing any additional config to be passed to the GS provider with a contact",
    )


def add_env_flag(parser: Any) -> None:
    parser.add_argument(
        "environment",
        type=str,
        # choices=ENVS,
        help=(
            "Which environment to configure."
            "Either 'production' or 'staging' except for diff which can take in both as a list."
        ),
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
            "R|The channels to act on in one of three different formats.\n"
            "1) As a comma separated list of literal channel names.\n\n"
            "2) A predicate in the form of a Python conditional statement \n"
            "filtering channels based on their classification annotations. \n\n"
            "* Some notes *\n"
            "- The annotations must be referred directly by the field name. \n"
            "- The statement is executed without any modifications. \n"
            "- It must be valid Python. \n"
            "- It must use correct types and the exact values it needs to match. \n"
            "  For example, using 'bidir' instead of 'BIDIR' or the string '39' \n"
            "  instead of integer 39 will not work as expected. Boolean fields \n"
            "  can be used as bools. \n"
            "- Anything Python supports is supported. e.g. `and`, `not`, `or` keywords,\n"
            "  parantheses.\n"
            "e.g. this statement will select both BIDIRs that cannot run rpcs and \n"
            "39PLS DVB S-Band channels:\n"
            "'(directionality == 'BIDIR' and not can_run_rpcs) or \n"
            "space_ground_sband_dvbs2x_pls == 39'\n\n"
            "For more examples, see the groups in contact_type_defs.yaml.\n\n"
            f"3) The following aliases: {aliases} or 'all'.\n"
        ),
    )


def add_auto_update_flags(parser: Any) -> None:
    parser.add_argument(
        "--parameter",
        type=str,
        choices={
            "link_profile",
            "contact_overhead_time",
        },  # TODO: contact_overhead_time
        help="Which config parameter to auto-update",
        required=True,
    )

    parser.add_argument(
        "--data-column",
        type=str,
        help="Name of the column that stores historic values. Must match exactly",
        required=True,
    )

    parser.add_argument(
        "--conversion-factor",
        type=float,
        help="The factor by which individual values will be multiplied by. e.g. if your data is in kilobytes but output should be in megabytes, pass in 0.001",
        default=1.0,
    )

    parser.add_argument(
        "--calculation-method",
        type=str,
        choices={"ema", "sma"},
        help="Calculation method for new values. Exponential moving average or simple moving average",
        default="ema",
    )

    parser.add_argument(
        "--safety-factor",
        type=float,
        help="Multiplier for the updated parameter, to enable conservative under-estimation. Should be between 0 and 1.",
        default=1,
    )

    parser.add_argument(
        "--source-file",
        type=str,
        help="The CSV file containing historical data",
    )


def add_asset_flags(parser: Any) -> None:
    add_env_flag(parser)
    add_asset_flag(parser)
    add_channel_flag(parser)


# These are separated to a function since other subcommands that might need to
# call pls tool's internal functions will need to pass these and we need a
# single source of truth for defaults.
def add_pls_flags(parser: Any) -> None:
    parser.add_argument(
        "--iovdb",
        help="SnR db adjustment based on IOV (default %(default).1f, change with care)",
        default=4,
        type=float,
    )
    parser.add_argument(
        "template",
        nargs="?",
        help="YAML template to expand",
        default="fragments/txo_dvb_template.yaml",
    )


# Allow newlines in help texts that starts with the R| marker
# format as usual otherwise
class ArgFormatter(argparse.HelpFormatter):
    def _split_lines(self, text: str, width: int) -> list[str]:
        if text.startswith("R|"):
            return text[2:].splitlines()
        return argparse.HelpFormatter._split_lines(self, text, width)


PARSER = argparse.ArgumentParser(
    prog="python -m channel_tool",
    description="A utility to help with managing channels.",
    formatter_class=ArgFormatter,
)
PARSER.add_argument("--debug", action="store_true", help="Run in debugging mode.")

SUBPARSERS = PARSER.add_subparsers()


def add_subparser(*args, **kwargs) -> argparse.ArgumentParser:  # type: ignore
    return SUBPARSERS.add_parser(
        *args,
        **kwargs,
        formatter_class=ArgFormatter,
    )


ADD_PARSER = add_subparser(
    "add",
    help="Add a channel configuration from a template.",
    aliases=["a"],
)
ADD_PARSER.set_defaults(func=add_config)
add_process_flags(ADD_PARSER)
add_editing_flags(ADD_PARSER)
add_asset_flags(ADD_PARSER)

DELETE_PARSER = add_subparser(
    "delete",
    help="Delete a channel configuration.",
    aliases=["d"],
)
DELETE_PARSER.set_defaults(func=delete_config)
add_process_flags(DELETE_PARSER)
add_delete_flags(DELETE_PARSER)
add_asset_flags(DELETE_PARSER)

RENAME_PARSER = add_subparser(
    "rename",
    help="Rename a channel across all environments, assets and templates.",
    aliases=["r"],
)
RENAME_PARSER.set_defaults(func=rename_channel)
RENAME_PARSER.add_argument(
    "current_name",
    type=str,
    help=("current name of channel"),
)
RENAME_PARSER.add_argument(
    "new_name",
    type=str,
    help=("new name for channel"),
)


EDIT_PARSER = add_subparser(
    "edit",
    help="Modify an existing channel configuration.",
    aliases=["e"],
)
EDIT_PARSER.set_defaults(func=edit_config)
add_process_flags(EDIT_PARSER)
add_editing_flags(EDIT_PARSER)
add_asset_flags(EDIT_PARSER)

AUDIT_PARSER = add_subparser(
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

QUERY_PARSER = add_subparser(
    "query",
    help="Query field values across assets and channels and output to CSV (only flat fields at the moment).",
)
QUERY_PARSER.set_defaults(func=query_configs)
add_env_flag(QUERY_PARSER)
add_asset_flag(QUERY_PARSER)
add_channel_flag(QUERY_PARSER)
QUERY_PARSER.add_argument(
    "field",
    type=str,
    help=("The field to query."),
)

DIFF_PARSER = add_subparser(
    "diff",
    help="Compare items.",
)
DIFF_PARSER.set_defaults(func=diff_configs)
add_env_flag(DIFF_PARSER)
add_asset_flag(DIFF_PARSER)
DIFF_PARSER.add_argument(
    "-v",
    "--verbose",
    action="store_const",
    const=2,
    default=1,
    help=("Increase verbosity of diff and print changed values."),
)

NORMALIZE_PARSER = add_subparser(
    "normalize", help="Silently convert specific configurations to a normalized format."
)
NORMALIZE_PARSER.set_defaults(func=normalize_configs)
add_env_flag(NORMALIZE_PARSER)
add_asset_flag(NORMALIZE_PARSER)

FORMAT_PARSER = add_subparser(
    "format",
    help="Normalize all configuration formatting, indicating which files were changed.",
)
FORMAT_PARSER.set_defaults(func=format_configs)
FORMAT_PARSER.add_argument(
    "--check",
    action="store_true",
    help=("Report if any configs would be updated for formatting and fail if so."),
)

VALIDATE_PARSER = add_subparser(
    "validate", help="Validate all templates and extant configurations."
)
VALIDATE_PARSER.add_argument(
    "-m", "--module", help="Validation rule module substring", type=str, required=False
)
VALIDATE_PARSER.add_argument(
    "-f",
    "--function",
    help="Validation rule function name substring",
    type=str,
    required=False,
)
VALIDATE_PARSER.add_argument(
    "-a",
    "--assets",
    help=(
        "The satellites or ground stations to validate. "
        "Can be a comma separated list of asset IDs, 'all_gs', 'all_sat', or 'all'."
    ),
    type=str,
    required=False,
)
VALIDATE_PARSER.set_defaults(func=lambda args: validate_all(args))

AUTO_UPDATE_PARSER = add_subparser(
    "auto-update",
    help="Automatically update link profiles for given assets and channels.",
)
AUTO_UPDATE_PARSER.set_defaults(func=auto_update_config)
add_auto_update_flags(AUTO_UPDATE_PARSER)
add_asset_flags(AUTO_UPDATE_PARSER)
add_process_flags(AUTO_UPDATE_PARSER)

DUPLICATE_PARSER = add_subparser(
    "duplicate",
    help=(
        "R|Duplicate a channel within an asset with a different PLS value.\n"
        "- A channel can only be duplicated within the same asset.\n"
        "- It is currently not possible to duplicate while changing bandwidths.\n"
        "- If more than one channel to duplicate is specified, only the first one will be used.\n"
    ),
)
DUPLICATE_PARSER.set_defaults(func=duplicate_config)
add_asset_flags(DUPLICATE_PARSER)
add_process_flags(DUPLICATE_PARSER)
add_pls_flags(DUPLICATE_PARSER)
DUPLICATE_PARSER.add_argument("--pls", help="New PLS value", type=int, required=True)
# TODO we have a pls to bitrate mapping in pls tool we can use instead
DUPLICATE_PARSER.add_argument(
    "--bitrate-kbps", help="New bitrate in kbps", type=float, required=True
)
DUPLICATE_PARSER.add_argument(
    "--min-elevation-deg",
    help="New minimum elevation in degrees",
    type=float,
    required=True,
)

PLS_PARSER = add_subparser(
    "pls",
    help="Look up PLS-associated values",
)
PLS_PARSER.set_defaults(func=pls_lookup)
add_pls_flags(PLS_PARSER)
PLS_LOOKUP = PLS_PARSER.add_mutually_exclusive_group(required=True)
PLS_LOOKUP.add_argument("-p", "--pls", help="PLS value", type=int)
PLS_LOOKUP.add_argument("-d", "--db", help="SnR value (db)", type=float)
PLS_BAND = PLS_PARSER.add_mutually_exclusive_group(required=False)
PLS_BAND.add_argument(
    "-s",
    "--sband",
    help=f"SBand mode.  Valid PLS values are {sorted(pls_short)}",
    action="store_true",
)
PLS_BAND.add_argument(
    "-x",
    "--xband",
    help=f"XBand mode.  Valid PLS values are {sorted(pls_long)}",
    action="store_true",
)
PLS_PARSER.add_argument(
    "--raw",
    help="Print the raw result without any comments",
    default=False,
    action="store_true",
)
PLS_PARSER.add_argument("--bidir", action="store_true", default=False)
PLS_PARSER.add_argument(
    "-r", "--radionet", help="enable radionet", default=False, action="store_true"
)

DATABASE_PARSER = add_subparser(
    "db", help="[EXPERIMENTAL] Interact with SQL config database"
)
DATABASE_SUBPARSERS = DATABASE_PARSER.add_subparsers()

DATABASE_INIT_PARSER = DATABASE_SUBPARSERS.add_parser(
    "init", help="Create a new SQLite database with existing data"
)
DATABASE_INIT_PARSER.set_defaults(func=lambda _: db.init())

DATABASE_SAMPLE_PARSER = DATABASE_SUBPARSERS.add_parser(
    "load-samples", help="Load sample data into the database"
)
DATABASE_SAMPLE_PARSER.set_defaults(func=lambda _: db.load_sample_data())

DATABASE_LICENSE_PARSER = DATABASE_SUBPARSERS.add_parser(
    "load-licenses", help="Load license data from YAML into the database"
)
DATABASE_LICENSE_PARSER.set_defaults(func=lambda _: db.load_license_data())

DATABASE_INGEST_PARSER = DATABASE_SUBPARSERS.add_parser(
    "ingest", help="Ingest a configuration file for a given asset into the database"
)
DATABASE_INGEST_PARSER.set_defaults(
    func=lambda args: db.ingest_assets(args.environment, args.assets)
)
add_env_flag(DATABASE_INGEST_PARSER)
add_asset_flag(DATABASE_INGEST_PARSER)

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
