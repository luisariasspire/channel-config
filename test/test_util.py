from util import lookup, set_path


def test_lookup():
    obj = {
        "foo": True,
        "bar": "baz",
        "quux": {
            "quibble": "bibble",
        },
    }

    assert lookup("foo", obj) is True
    assert lookup("bar", obj) == "baz"
    assert lookup("quux.quibble", obj) == "bibble"


def test_set_path():
    obj = {"foo": {"bar": False}}

    assert set_path("foo.bar", obj, True) == {"foo": {"bar": True}}
    assert set_path("quux", obj, True) == {"foo": {"bar": False}, "quux": True}
