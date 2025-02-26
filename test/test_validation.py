import pytest

from channel_tool.util import GROUND_STATION, SATELLITE, load_yaml_file
from channel_tool.validation import (
    SchemaValidationError,
    check_element_conforms_to_schema,
)


@pytest.mark.parametrize(
    "key,config", load_yaml_file("test/example_data/valid_gs_configs.yaml").items()
)
def test_validate_one_valid_gs_config(key, config):
    try:
        check_element_conforms_to_schema(
            GROUND_STATION, config, file="valid_gs_configs.yaml", key=key
        )
    except SchemaValidationError as e:
        raise SchemaValidationError(f"Failed to validate GS {key}") from e


@pytest.mark.parametrize(
    "key,config", load_yaml_file("test/example_data/broken_gs_configs.yaml").items()
)
def test_validate_one_broken_gs_config(key, config):
    try:
        check_element_conforms_to_schema(
            GROUND_STATION, config, file="broken_gs_configs.yaml", key=key
        )
        raise AssertionError(f"Expected SchemaValidationError for GS config {key}")
    except SchemaValidationError:
        pass


@pytest.mark.parametrize(
    "key,config", load_yaml_file("test/example_data/valid_sat_configs.yaml").items()
)
def test_validate_one_valid_sat_config(key, config):
    try:
        check_element_conforms_to_schema(
            SATELLITE, config, file="valid_sat_configs.yaml", key=key
        )
    except SchemaValidationError as e:
        raise SchemaValidationError(f"Failed to validate satellite {key}") from e


@pytest.mark.parametrize(
    "key,config", load_yaml_file("test/example_data/broken_sat_configs.yaml").items()
)
def test_validate_one_broken_sat_config(key, config):
    try:
        check_element_conforms_to_schema(
            SATELLITE, config, file="broken_sat_configs.yaml", key=key
        )
        raise AssertionError(
            f"Expected SchemaValidationError for satellite config {key}"
        )
    except SchemaValidationError:
        pass
