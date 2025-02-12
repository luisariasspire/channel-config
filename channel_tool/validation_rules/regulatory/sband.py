import re
from typing import Any, Dict, Optional, Union

from channel_tool.typedefs import ChannelDefinition
from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    get_nested,
    validation_rule,
)


def assert_same_allowed_license_countries(
    channel_configs: Dict[str, ChannelDefinition | None],
    parent_channel: str,
    variant_channel: str,
) -> bool:
    parent_allowed_countries = get_nested(
        channel_configs, [parent_channel, "allowed_license_countries"]
    )
    variant_allowed_countries = get_nested(
        channel_configs, [variant_channel, "allowed_license_countries"]
    )

    parent_enabled = get_nested(channel_configs, [parent_channel, "enabled"])
    variant_enabled = get_nested(channel_configs, [variant_channel, "enabled"])

    return (
        set(parent_allowed_countries) == set(variant_allowed_countries)
        and parent_enabled == variant_enabled
    )


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="Variants of CONTACT_BIDIR_PARAM_DVBS2X and CONTACT_RXO_DVBS2X must have the same allowed_license_countries and be disabled if the parent is disabled",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def gs_variants_of_contact_bidir_param_dvbs2x_and_contact_rxo_dvbs2x_must_have_the_same_allowed_license_countries(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if (
        channel_id != "CONTACT_BIDIR_PARAM_DVBS2X"
        and channel_id != "CONTACT_RXO_DVBS2X"
    ):
        return True

    channel_configs = input.gs_configs[gs_id]

    regex = re.compile(f"^{channel_id}.*DEG$")
    variant_channels = [
        channel_id for channel_id in channel_configs.keys() if regex.match(channel_id)
    ]
    validation_results = [
        assert_same_allowed_license_countries(
            channel_configs, channel_id, variant_channel
        )
        for variant_channel in variant_channels
    ]

    return all(validation_results)


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_CHANNEL,
    description="Variants of CONTACT_BIDIR_PARAM_DVBS2X and CONTACT_RXO_DVBS2X must have the same allowed_license_countries and be disabled if the parent is disabled",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def sat_variants_of_contact_bidir_param_dvbs2x_and_contact_rxo_dvbs2x_must_have_the_same_allowed_license_countries(
    input: ValidationRuleInput,
    sat_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if (
        channel_id != "CONTACT_BIDIR_PARAM_DVBS2X"
        and channel_id != "CONTACT_RXO_DVBS2X"
    ):
        return True

    channel_configs = input.sat_configs[sat_id]

    regex = re.compile(f"^{channel_id}.*DEG$")
    variant_channels = [
        channel_id for channel_id in channel_configs.keys() if regex.match(channel_id)
    ]
    validation_results = [
        assert_same_allowed_license_countries(
            channel_configs, channel_id, variant_channel
        )
        for variant_channel in variant_channels
    ]

    return all(validation_results)
