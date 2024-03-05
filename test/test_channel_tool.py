from channel_tool.__main__ import merge, remove, str_to_bool, update


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


def test_remove_lists_simple():
    a = [1, 2, 3]
    b = [3, 4, 5]
    c = remove(a, b)
    assert c == [1, 2]


def test_remove_lists_complete_deletion():
    a = [1, 2, 3]
    b = [1, 2, 3]
    c = remove(a, b)
    assert c == []


def test_remove_dicts_simple():
    a = {"a": 1, "b": 2, "c": 3}
    b = {"b": 3, "c": 4, "d": 5}
    c = remove(a, b)
    assert c == {"a": 1, "b": 2, "c": 3}


def test_remove_dicts_complete_deletion():
    a = {"a": 1, "b": 2, "c": 3}
    b = {"a": 1, "b": 2, "c": 3}
    c = remove(a, b)
    assert c == {}


def test_remove_dicts_recursive():
    a = {"a": {"a1": 1, "a2": 2}, "b": {"b1": 1}}
    b = {"a": {"a2": 2}, "b": {"b1": 3, "b2": 2}}
    c = remove(a, b)
    assert c == {"a": {"a1": 1}, "b": {"b1": 1}}


def test_remove_mixed_dicts_and_lists_preserving_substructure():
    a = {
        "a": [2],
        "b": [1, 3],
        "c": [{"c1": 2}, {"c1": 3}, {"c2": 4}],
        "d": [4],
        "e": [5],
    }
    b = {"a": [1], "b": [1], "c": [{"c1": 2}], "e": [5]}
    c = remove(a, b)
    # Note that the "c" sequence is only modified when there's a perfect match
    assert c == {"a": [2], "b": [3], "c": [{"c1": 3}, {"c2": 4}], "d": [4]}


def test_remove_primitive_not_equal():
    a = 1
    b = 2
    c = remove(a, b)
    assert c == 1


def test_remove_primitive_equal():
    a = 1
    b = 1
    c = remove(a, b)
    assert c == None


def test_remove_string():
    a = "abc"
    b = "abc"
    c = remove(a, b)
    assert c == None


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


def test_update_lists_simple():
    a = [1, 2, 3, 4]
    b = [3, 4, 5]
    c = update(a, b)
    assert c == [3, 4, 5]  # Lists will be replaced


def test_update_dicts_simple():
    a = {"a": 1, "b": 2, "c": 3}
    b = {"c": 4, "d": 5}
    c = update(a, b)
    assert c == {"a": 1, "b": 2, "c": 4}  # Not allowed to add fields with update


def test_update_dicts_recursive():
    a = {"a": {"a1": 1}, "b": {"b1": 1}}
    b = {"a": {"a2": 1}, "b": {"b1": 2}, "d": {"d1": 1}}
    c = update(a, b)
    # Can't add fields recursively neither
    assert c == {"a": {"a1": 1}, "b": {"b1": 2}}


def test_update_mixed_dicts_and_lists():
    a = {"a": [1], "b": [1]}
    b = {"a": [2], "b": [1, 3], "d": [4]}
    c = update(a, b)
    assert c == {"a": [2], "b": [1, 3]}  # Again, d is ignored


def test_update_list_of_dicts():
    a = [{"a": 1, "b": 2, "c": 3}, {"a": 2, "b": 3, "c": 4}]
    b = [{"b": 4, "c": None}]
    c = update(a, b)
    # No predicate -> update everything
    assert c == [{"a": 1, "b": 4, "c": 3}, {"a": 2, "b": 4, "c": 4}]


def test_update_list_of_dicts_predicate():
    a = [{"a": 1, "b": 2, "c": 3}, {"a": 2, "b": 3, "c": 4}]
    b = [{"a": None, "b": 4}]
    p = [lambda config: config["a"] <= 1]
    c = update(a, b, p)
    # First one holds, update. Second one does not hold, don't update.
    assert c == [{"a": 1, "b": 4, "c": 3}, {"a": 2, "b": 3, "c": 4}]


def test_update_list_of_dicts_predicate_two():
    a = [{"a": 1, "b": 2, "c": 3}, {"a": 2, "b": 3, "c": 4}]
    b = [{"b": 4, "c": None}]
    p = [lambda config: config["a"] >= 1, lambda config: config["b"] > 2]
    c = update(a, b, p)
    # First one only matches one predicate, second one matches both. Update second only
    assert c == [{"a": 1, "b": 2, "c": 3}, {"a": 2, "b": 4, "c": 4}]
