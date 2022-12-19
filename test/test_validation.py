import pytest

from channel_tool.util import load_yaml_file
from channel_tool.validation import ValidationError, validate_one


@pytest.mark.parametrize(
    "key,config", load_yaml_file("test/example_data/valid_configs.yaml").items()
)
def test_validate_one_valid_config(key, config):
    try:
        validate_one(config, file="valid_configs.yaml", key=key)
    except ValidationError as e:
        raise ValidationError(f"Failed to validate {key}") from e


@pytest.mark.parametrize(
    "key,config", load_yaml_file("test/example_data/broken_configs.yaml").items()
)
def test_validate_one_broken_config(key, config):
    try:
        validate_one(config, file="broken_configs.yaml", key=key)
        raise AssertionError(f"Expected ValidationError for config {key}")
    except ValidationError:
        pass
