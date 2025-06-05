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


@validation_rule(
    scope=ValidationRuleScope.GENERAL,
    description="Example rule with general scope",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def uhf_must_be_first_window_param_in_s_u_bidir(
    input: ValidationRuleInput,
) -> Union[str, bool]:
    bidir_channel_ids = {
        id
        for id, config in input.gs_templates.items()
        if config["classification_annotations"]["directionality"] == "BIDIR"
        and config["classification_annotations"]["space_ground_sband"]
    }

    all_configs = input.gs_configs
    all_configs.update(input.sat_configs)
    all_configs = {
        asset_id: {
            id: config for id, config in configs.items() if id in bidir_channel_ids
        }
        for asset_id, configs in all_configs.items()
    }

    channel_id_to_configs: dict[str, dict[str, ChannelDefinition]] = {}

    for asset_id, configs in all_configs.items():
        for id, config in configs.items():
            window_params = config.get("window_parameters", None)

            if not window_params:
                continue

            channel_id_to_configs.setdefault(id, {})[asset_id] = config

    errors = set()
    for channel_id, configs in channel_id_to_configs.items():
        for asset_id, config in configs.items():
            window_params = config["window_parameters"]
            forward_channels = window_params["forward_channels"]

            if (
                forward_channels[0]["radio_band"] != "UHF"
                or forward_channels[1]["radio_band"] != "SBAND"
            ):
                errors.add(f"{channel_id} on {asset_id}")

    if errors:
        return f"Following channels has incorrect UHF/SBAND forward channel order:\n{errors}"

    return True


@validation_rule(
    scope=ValidationRuleScope.GENERAL,
    description="Example rule with general scope",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def s_u_bidir_must_have_correct_number_of_channels(
    input: ValidationRuleInput,
) -> Union[str, bool]:
    bidir_channel_ids = {
        id
        for id, config in input.gs_templates.items()
        if config["classification_annotations"]["directionality"] == "BIDIR"
        and config["classification_annotations"]["space_ground_sband"]
    }

    all_configs = input.gs_configs
    all_configs.update(input.sat_configs)
    all_configs = {
        asset_id: {
            id: config for id, config in configs.items() if id in bidir_channel_ids
        }
        for asset_id, configs in all_configs.items()
    }

    errors = set()
    for asset_id, configs in all_configs.items():
        for id, config in configs.items():
            window_params = config.get("window_parameters", None)

            if not window_params:
                continue

            if (
                len(window_params["forward_channels"]) != 2
                or len(window_params["reverse_channels"]) != 1
            ):
                errors.add(f"{id} on {asset_id}")

    if errors:
        return f"Following channels does not have the correct number of forward/reverse channels:\n{errors}"

    return True
