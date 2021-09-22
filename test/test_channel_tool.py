from channel_tool import merge, str_to_bool


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


def test_str_to_bool_converts_expected_true_inputs_correctly():
    true_cases = [
        "true",
        "yes",
        "1",
        "True",
        "Y",
    ]
    for case in true_cases:
        assert str_to_bool(case)


def test_str_to_bool_converts_expected_false_inputs_correctly():
    false_cases = [
        "false",
        "no",
        "0",
        "FALSE",
        "N",
    ]
    for case in false_cases:
        assert not str_to_bool(case)


def test_str_to_bool_errors_on_unexpected_inputs():
    cases = [
        "asdf",
        "flase",
        "tru",
        "z",
        "N0",
    ]
    for case in cases:
        try:
            result = str_to_bool(case)
            assert False, f"Expected error on input {case}, got {result}"
        except ValueError:
            pass
