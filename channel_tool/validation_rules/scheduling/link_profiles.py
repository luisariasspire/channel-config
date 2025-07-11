from typing import Any, Dict, Union

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    validation_rule,
)


def check_link_profile_number_and_elevation(
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    link_profiles = channel_config["link_profile"]
    num_link_profiles = len(link_profiles)
    if class_annos["space_ground_sband"] and class_annos["ground_space_uhf"]:
        # SBand bidirs should have a UHF link profile first and an S-band link profile second,
        # with the UHF min elevation no greater than the S-band min elevation for any FM.
        if num_link_profiles != 2:
            return f"S/U bidirs expected to have precisely 2 link profiles (UHF, then S-band) but {num_link_profiles} were found"
        uhf_link_profile = link_profiles[0]
        sband_link_profile = link_profiles[1]
        uhf_default_min_elev = uhf_link_profile.get("min_elevation_deg", None)
        if not uhf_default_min_elev:
            uhf_default_min_elev = uhf_link_profile["default_min_elevation_deg"]
        sband_default_min_elev = sband_link_profile.get("min_elevation_deg", None)
        if not sband_default_min_elev:
            sband_default_min_elev = sband_link_profile["default_min_elevation_deg"]
        if sband_default_min_elev < uhf_default_min_elev:
            return f"S-band default min elevation of {sband_default_min_elev} should not be less than UHF default min elevation of {uhf_default_min_elev}"
        # For satellites named in the link profile, create a map of sat ID to pair
        # of (<UHF min elevation>, <S-band min elevation>)
        sat_id_to_elev_pair = {}
        for s_min_elev in uhf_link_profile.get("satellite_min_elevations", []):
            for sat_id in s_min_elev["satellites"]:
                sat_id_to_elev_pair[sat_id] = (
                    s_min_elev["min_elevation_deg"],
                    sband_default_min_elev,
                )
        for s_min_elev in sband_link_profile.get("satellite_min_elevations", []):
            for sat_id in s_min_elev["satellites"]:
                elev_pair = sat_id_to_elev_pair.get(
                    sat_id, (uhf_default_min_elev, sband_default_min_elev)
                )
                elev_pair = (elev_pair[0], s_min_elev["min_elevation_deg"])
                sat_id_to_elev_pair[sat_id] = elev_pair
        sats_with_invalid_pair = [
            sat_elev_pair[0]
            for sat_elev_pair in sat_id_to_elev_pair.items()
            if sat_elev_pair[1][0] > sat_elev_pair[1][1]
        ]
        if len(sats_with_invalid_pair) > 0:
            return f"Effective min elevation greater for UHF than for S-band for these satellites: {sats_with_invalid_pair}"
    else:
        if num_link_profiles != 1:
            return f"Only 1 link profile expected for this class of contact but {num_link_profiles} were found"
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Check link profile number and elvations in groundstation templates",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def check_link_profile_number_and_elevation_in_groundstation_templates(
    input: ValidationRuleInput,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return check_link_profile_number_and_elevation(class_annos, channel_config)


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="Check link profile number and elvations in groundstation channels",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def check_link_profile_number_and_elevation_in_groundstation_channels(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return check_link_profile_number_and_elevation(class_annos, channel_config)


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="Check link profile elevation overrides are unique",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def check_link_profile_elevation_overrides_unique(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    link_profiles = channel_config["link_profile"]

    if "satellite_min_elevations" not in link_profiles[0]:
        return True

    overrides = [
        x["min_elevation_deg"]
        for lp in link_profiles
        for x in lp["satellite_min_elevations"]
    ]

    duplicates = [x for x in set(overrides) if overrides.count(x) > 1]

    if duplicates:
        return f"Elevation(s) {duplicates} were mentioned multiple times in the link profile"

    return True
