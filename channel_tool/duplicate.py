from copy import deepcopy
from enum import Enum
from types import SimpleNamespace
from typing import Any

from channel_tool.naming import class_annos_to_name
from channel_tool.pls_tool import pls_lookup
from channel_tool.typedefs import ChannelDefinition


class DuplicateError(Exception):
    pass


class Band(Enum):
    S = 1
    X = 2


class Directionality(Enum):
    TXO = 1
    BIDIR = 2


class DuplicateArgs:
    directionality: Directionality
    pls: int
    bw_mhz: Any
    band: Band
    bitrate_kbps: float
    min_elevation: float
    iovdb: bool
    template: str

    def __init__(self, args: SimpleNamespace, class_annos: dict[str, Any]):
        self.pls = args.pls
        self.min_elevation = args.min_elevation_deg
        self.bitrate_kbps = args.bitrate_kbps
        self.bw_mhz = class_annos.get(
            "space_ground_xband_bandwidth_mhz"
        ) or class_annos.get("space_ground_sband_bandwidth_mhz")
        self.band = Band.S if class_annos.get("space_ground_sband") else Band.X
        self.directionality = Directionality[class_annos["directionality"]]
        self.iovdb = args.iovdb
        self.template = args.template


def merge_forward_channels(d1: dict[Any, Any], d2: dict[Any, Any]) -> dict[Any, Any]:
    """
    Merge two forward channel definitions, giving priority to d2
    Doesn't cover most edge cases of merging arbitrary dicts
    Replaces the value with d2's for shared keys for all types
    except for dicts which are recursed.
    TODO: merge function from main could be used instead but I don't yet know
    if the behavior matches
    """
    assert isinstance(d1, dict) and isinstance(d2, dict)
    d = deepcopy(d1)
    for key in d2:
        if key not in d1:
            d[key] = d2[key]
        elif isinstance(d1[key], dict) and isinstance(d2[key], dict):
            merged = merge_forward_channels(d1[key], d2[key])
            d[key] = merged
        elif type(d1[key]) != type(d2[key]):
            raise DuplicateError(
                "The same forward channel key has values of different type."
            )
        else:
            d[key] = d2[key]

    return d


def update_nested_value(
    d: dict[str, Any], keys: tuple[str, ...], new_value: Any
) -> dict[Any, Any]:
    """
    Update a nested value at the specified path, returning a new copy of d.
    A key that doesn't exist in d will be created.
    Raises an exception if d or keys is empty.

    Args:
        d: dictionary to update
        keys: Tuple of nested keys e.g. ('a', 'b', 'c') corresponds to `d['a']['b']['c']`
        new_value: The new value to set

    Returns:
        A new dictionary with the specified path updated.
    """
    if not keys or not d:
        raise DuplicateError("`d` and `keys` must be populated!")

    # deepcopy the input to make sure we don't carry over any references this
    # needs to be done once so it is wasteful for recursive calls but it'd be a
    # risk to have the caller handle it
    new_value = deepcopy(new_value)
    key = keys[0]

    if len(keys) == 1:
        return {**d, key: new_value}
    else:
        return {**d, key: update_nested_value(d[key], keys[1:], new_value)}


def update_multiple_nested_values(
    d: dict[str, Any], updates: dict[tuple[str, ...], Any]
) -> dict[Any, Any]:
    """
    Update multiple nested values at specified paths, returning a new copy of d.
    Raises an exception if:
        - d or any of the update paths are empty
        - one of the keys on the path does not exist in d

    Args:
        d: dictionary to update
        updates: dictionary of paths to new values. See `duplicate.update_nested_value` for how paths are interpreted.
            e.g. {('a', 'b', 'c'): 10, ('d'): "new_value"}

    Returns:
        A new dictionary with the specified paths updated.
    """

    result = {**d}

    for keys, new_value in updates.items():
        result = update_nested_value(result, keys, new_value)

    return result


def duplicate_class_annos(
    args: DuplicateArgs, original_class_annos: dict[str, Any]
) -> dict[str, Any]:
    band = args.band.name.lower()
    key = f"space_ground_{band}band_dvbs2x_pls"
    return update_nested_value(original_class_annos, (key,), args.pls)


# Get the appropriate forward channel definition from pls_tool
def gen_forward_channel(args: DuplicateArgs) -> Any:
    pls_args = {
        "sband": args.band == Band.S,
        "xband": args.band == Band.X,
        "pls": args.pls,
        "iovdb": args.iovdb,
        "template": args.template,
        "radionet": True,
        "raw": False,
    }

    obj = SimpleNamespace(**pls_args)

    return pls_lookup(obj, False)


def duplicate_link_profile(
    args: DuplicateArgs, original_link_profile: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    dvb_profile = max(original_link_profile, key=lambda i: i["downlink_rate_kbps"])

    link_profile = [
        update_multiple_nested_values(
            dvb_profile,
            {
                ("min_elevation_deg",): float(args.min_elevation),
                ("downlink_rate_kbps",): args.bitrate_kbps,
            },
        )
    ]

    if args.directionality == Directionality.BIDIR:
        uhf_profile = min(original_link_profile, key=lambda i: i["downlink_rate_kbps"])

        link_profile.append(uhf_profile)

    return link_profile


def duplicate_dynamic_window_parameters(
    args: DuplicateArgs, original_dynamic_window_parameters: dict[Any, Any]
) -> dict[Any, Any]:
    result = {**original_dynamic_window_parameters}

    if original_dynamic_window_parameters.get("transmit_times", {}).get(
        "elevation_threshold_deg", None
    ):
        result = update_nested_value(
            result, ("transmit_times", "elevation_threshold_deg"), args.min_elevation
        )

    return result


def duplicate_window_parameters(
    args: DuplicateArgs, original_window_parameters: dict[Any, Any]
) -> Any:
    original_dvb_forward_channel = [
        fc
        for fc in original_window_parameters.get("forward_channels", [])
        if fc.get("radio_band", "") != "UHF"
    ]

    forward_channel_overrides = gen_forward_channel(args)["forward_channels"][0]

    # We need to add the values from the pls tool even if the original did not
    # have any window parameters since non-default pls values must specify
    # those fields
    if not original_dvb_forward_channel:
        return forward_channel_overrides

    og_dvb_forward_channel = original_dvb_forward_channel[0]

    forward_channels = []

    if args.directionality == Directionality.BIDIR:
        forward_channels.append({"radio_band": "UHF"})

    dvb_forward_channel = merge_forward_channels(
        og_dvb_forward_channel, forward_channel_overrides
    )

    forward_channels.append(dvb_forward_channel)

    return update_nested_value(
        original_window_parameters, ("forward_channels",), forward_channels
    )


def check_duplicate_supported(classification_annotations: dict[str, Any]) -> None:
    if classification_annotations.get("ground_space_sband"):
        raise DuplicateError("duplicate does not support S/X BIDIRs!")

    if not (
        classification_annotations.get("space_ground_xband_dvbs2x_pls")
        or classification_annotations.get("space_ground_sband_dvbs2x_pls")
    ):
        raise DuplicateError("Only DVB channels can be duplicated!")


def gen_channel_id(args: Any, template_class_annos: dict[Any, Any]) -> Any:
    args = DuplicateArgs(args, template_class_annos)
    new_class_annos = duplicate_class_annos(args, template_class_annos)

    return class_annos_to_name(new_class_annos)


def duplicate(
    args: Any, existing: ChannelDefinition, template_class_annos: dict[Any, Any]
) -> dict[Any, Any]:
    check_duplicate_supported(template_class_annos)

    args = DuplicateArgs(args, template_class_annos)

    # TODO: This depends on the software version. We might pull that information
    # from Databricks.
    contact_overhead_time = "10s"

    original_class_annos = existing.get("classification_annotations", {})

    class_annos = None
    # Satellites don't have class annos
    if original_class_annos:
        class_annos = duplicate_class_annos(args, original_class_annos)

    original_link_profile = existing.get("link_profile")

    # Satellites don't have link profiles
    link_profile = None
    if original_link_profile:
        link_profile = duplicate_link_profile(args, original_link_profile)

    original_window_parameters = existing.get("window_parameters", {})

    window_parameters = duplicate_window_parameters(
        args,
        original_window_parameters,
    )

    original_dynamic_window_parameters = existing.get("dynamic_window_parameters", {})

    dynamic_window_parameters = duplicate_dynamic_window_parameters(
        args, original_dynamic_window_parameters
    )

    updates: dict[tuple[str, ...], Any] = {
        ("contact_overhead_time",): contact_overhead_time,
    }

    if link_profile:
        updates[("link_profile",)] = link_profile

    if class_annos:
        updates[("classification_annotations",)] = class_annos

    if window_parameters:
        updates[("window_parameters",)] = window_parameters

    if dynamic_window_parameters:
        updates[("dynamic_window_parameters",)] = dynamic_window_parameters

    return update_multiple_nested_values(existing, updates)
