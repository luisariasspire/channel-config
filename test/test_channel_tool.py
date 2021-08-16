from channel_tool import ValidationError, merge, validate_one
from util import load_yaml_file


def test_validate_one():
    broken_configs = load_yaml_file("test/example_data/broken_configs.yaml")
    for key, config in broken_configs.items():
        try:
            validate_one(config)
            raise AssertionError(f"Expected ValidationError for config {key}")
        except ValidationError:
            pass


def test_merge_lists_simple():
    a = [1, 2, 3]
    b = [3, 4, 5]
    c = merge(a, b)
    assert c == [1, 2, 3, 4, 5]


def test_merge_dicts_simple():
    a = {"a": 1, "b": 2, "c": 3}
    b = {"c": 4, "d": 5}
    c = merge(a, b)
    assert c == {"a": 1, "b": 2, "c": 4, "d": 5}


def test_merge_dicts_recursive():
    a = {"a": {"a1": 1}, "b": {"b1": 1}}
    b = {"a": {"a2": 1}, "b": {"b1": 2}, "d": {"d1": 1}}
    c = merge(a, b)
    assert c == {"a": {"a1": 1, "a2": 1}, "b": {"b1": 2}, "d": {"d1": 1}}


def test_merge_mixed_dicts_and_lists():
    a = {"a": [1], "b": [1]}
    b = {"a": [2], "b": [1, 3], "d": [4]}
    c = merge(a, b)
    assert c == {"a": [1, 2], "b": [1, 3], "d": [4]}
