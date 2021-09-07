from util import load_yaml_file
from validation import ValidationError, validate_one


def test_validate_one():
    broken_configs = load_yaml_file("test/example_data/broken_configs.yaml")
    for key, config in broken_configs.items():
        try:
            validate_one(config)
            raise AssertionError(f"Expected ValidationError for config {key}")
        except ValidationError:
            pass
