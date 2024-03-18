import pytest

from channel_tool.util import GROUND_STATION, SATELLITE, load_yaml_file
from channel_tool.validation import ValidationError, validate_one


@pytest.mark.parametrize(
    "key,config", load_yaml_file("test/example_data/valid_gs_configs.yaml").items()
)
def test_validate_one_valid_gs_config(key, config):
    try:
        validate_one(GROUND_STATION, config, file="valid_gs_configs.yaml", key=key)
    except ValidationError as e:
        raise ValidationError(f"Failed to validate GS {key}") from e


@pytest.mark.parametrize(
    "key,config", load_yaml_file("test/example_data/broken_gs_configs.yaml").items()
)
def test_validate_one_broken_gs_config(key, config):
    try:
        validate_one(GROUND_STATION, config, file="broken_gs_configs.yaml", key=key)
        raise AssertionError(f"Expected ValidationError for GS config {key}")
    except ValidationError:
        pass


@pytest.mark.parametrize(
    "key,config", load_yaml_file("test/example_data/valid_sat_configs.yaml").items()
)
def test_validate_one_valid_sat_config(key, config):
    try:
        validate_one(SATELLITE, config, file="valid_sat_configs.yaml", key=key)
    except ValidationError as e:
        raise ValidationError(f"Failed to validate satellite {key}") from e


@pytest.mark.parametrize(
    "key,config", load_yaml_file("test/example_data/broken_sat_configs.yaml").items()
)
def test_validate_one_broken_sat_config(key, config):
    try:
        validate_one(SATELLITE, config, file="broken_sat_configs.yaml", key=key)
        raise AssertionError(f"Expected ValidationError for satellite config {key}")
    except ValidationError:
        pass
