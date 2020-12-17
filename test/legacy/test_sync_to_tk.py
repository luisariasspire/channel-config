from legacy.sync_to_tk import create_patch_for_asset


def test_create_patch_for_asset():
    asset = {
        "foo": False,
        "bar": True,
        "quux": True,
        "baz": {
            "zap": True,
        },
        "unrelated": True,
    }

    enabled = {"foo"}
    disabled = {frozenset({"quux"}), frozenset({"bar", "quux"}), frozenset({"baz.zap"})}
    fieldset, patch = create_patch_for_asset(asset, enabled, disabled)

    assert set(fieldset.keys()) == (set(asset.keys()) - {"unrelated", "baz"}) | {
        "baz.zap"
    }
    assert set(patch.keys()) == {"quux", "baz.zap", "foo"}
