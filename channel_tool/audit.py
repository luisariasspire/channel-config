from itertools import chain, zip_longest
from typing import Any, List, Optional, Tuple

from tabulate import tabulate
from termcolor import colored

from channel_tool.asset_config import load_asset_config
from channel_tool.tk import load_tk_asset
from channel_tool.typedefs import (
    AssetConfig,
    ChannelDefinition,
    Environment,
    TkGroundStation,
    TkSatellite,
)
from channel_tool.util import GROUND_STATION, SATELLITE, dump_yaml_string, lookup


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

    sat_override = sat_chan.get("contact_type")
    gs_override = gs_chan.get("contact_type")
    if sat_override and gs_override and sat_override != gs_override:
        return f"Contact type mismatch ({sat_override} vs {gs_override})"

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

    denied_gss = lookup("satellite_constraints.deny_ground_stations", sat_chan)
    denied_sats = lookup("ground_station_constraints.deny_satellites", gs_chan)

    if denied_sats and satellite["spire_id"] in denied_sats:
        return "Satellite in ground station deny list"

    if denied_gss and ground_station["gs_id"] in denied_gss:
        return "Ground station in satellite deny list"

    return None


def compare_channels(
    sat_config: AssetConfig,
    gs_config: AssetConfig,
    satellite: TkSatellite,
    ground_station: TkGroundStation,
    inspections: List[Any],
) -> Tuple[List[List[Optional[str]]], List[List[Optional[str]]]]:
    """Compare the configured channels for the given satellite and ground station."""
    shared: List[List[Optional[str]]] = []
    mismatched: List[List[Optional[str]]] = []

    channels = set(sat_config.keys()).union(set(gs_config.keys()))
    for chan in channels:
        sat_chan = sat_config.get(chan)
        gs_chan = gs_config.get(chan)

        reason = channel_rejection_reason(satellite, ground_station, sat_chan, gs_chan)

        if reason:
            mismatched.append([chan, reason])
        else:
            assert sat_chan is not None and gs_chan is not None
            annotations = [i.apply(sat_chan, gs_chan) for i in inspections]
            shared.append([chan, *annotations])

    shared = sorted(shared)
    mismatched = sorted(mismatched)
    return (shared, mismatched)


def merge_static_parameters(sat_params: Any, gs_params: Any) -> Any:
    """Merge static parameter sets recursively, using the same logic as the Contact Scheduler."""
    # The below logic is transcribed as directly as possible from the Optimizer's merge logic in
    # utils::json::merge.
    # fmt: off
    match (sat_params, gs_params):
        case (None, _):
            return gs_params
        case (bool(_), bool(_)) | (str(_), str(_)) | (int(_), int(_)) | (float(_), float(_)):
            return sat_params
        case (list(_), list(_)):
            return [
                merge_static_parameters(sp, gp)
                for (sp, gp) in zip_longest(sat_params, gs_params, fillvalue=None)
            ]
        case (dict(_), dict(_)):
            keys = chain(sat_params.keys(), gs_params.keys())
            return {
                k: merge_static_parameters(sat_params.get(k), gs_params.get(k))
                for k in keys
            }
        case _:
            return sat_params
    # fmt: on


class MergedParametersInspection:
    """Audit inspection which shows the merged channel parameters."""

    @staticmethod
    def header() -> str:
        return "Merged Parameters"

    def apply(
        self, sat_chan: ChannelDefinition, gs_chan: ChannelDefinition
    ) -> Optional[str]:
        sat_params = sat_chan.get("window_parameters", {})
        gs_params = gs_chan.get("window_parameters", {})

        merged_params = merge_static_parameters(sat_params, gs_params)

        merge_str: str = dump_yaml_string(merged_params)
        return merge_str


class ContactTypeInspection:
    """Audit inspection which shows the final contact type."""

    @staticmethod
    def header() -> str:
        return "Contact Type"

    def apply(
        self, sat_chan: ChannelDefinition, gs_chan: ChannelDefinition
    ) -> Optional[str]:
        sat_override: Optional[str] = sat_chan.get("contact_type")
        gs_override: Optional[str] = gs_chan.get("contact_type")

        if sat_override and not gs_override:
            return sat_override
        if gs_override and not sat_override:
            return gs_override
        if gs_override and sat_override and gs_override == sat_override:
            return gs_override
        if not sat_override and not gs_override:
            return "<default>"
        else:
            return colored("Contact type mismatch!", "red")


class SatelliteConstraintInspection:
    """Audit inspection which indicates when channels have satellite constraints."""

    @staticmethod
    def header() -> str:
        return "Constraints"

    def apply(
        self, sat_chan: ChannelDefinition, gs_chan: ChannelDefinition
    ) -> Optional[str]:
        if sat_chan.get("satellite_constraints") is not None:
            return "Note: Subject to satellite constraints"
        else:
            return None


class AuditReport:
    def __init__(
        self,
        env: Environment,
        sat_id: str,
        gs_id: str,
        inspections: Optional[List[Any]] = None,
    ):
        if inspections is None:
            inspections = [
                SatelliteConstraintInspection(),
                MergedParametersInspection(),
                ContactTypeInspection(),
            ]

        self.inspections = inspections
        self.sat_id = sat_id
        self.gs_id = gs_id

        sat_config = load_asset_config(env, sat_id)
        gs_config = load_asset_config(env, gs_id)
        satellite = load_tk_asset(env, SATELLITE, sat_id)
        ground_station = load_tk_asset(env, GROUND_STATION, gs_id)

        self.shared, self.mismatched = compare_channels(
            sat_config, gs_config, satellite, ground_station, inspections
        )

    def __str__(self) -> str:
        out = f"Audit summary for {self.sat_id} -> {self.gs_id}"
        sep = "=" * len(out)
        out = out + "\n" + sep + "\n\n"

        out += "\nValid Channels\n\n"
        if self.shared:
            headers = ["Channel", *[i.header() for i in self.inspections]]
            out += tabulate(self.shared, headers)
        else:
            out += colored("(No channels passed licensing rules)", "magenta")

        rejected_table = tabulate(self.mismatched, ["Channel", "Reason"])
        out += f"\n\nRejected Channels\n\n{rejected_table}\n"

        return out
