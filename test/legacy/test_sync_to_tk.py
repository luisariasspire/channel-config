from legacy.sync_to_tk import (
    CnfClause,
    SettingsConflictError,
    create_patch_for_asset,
    generate_settings_requirements,
    solve,
)


def freeze(sets):
    t = set()
    for s in sets:
        t.add(frozenset(s))
    return t


def test_generate_settings_requirements():
    cfg = {
        "A": {"enabled": True},
        "B": {"enabled": False},
        "C": {"enabled": False},
        "D": {"enabled": False},
    }
    channel_reqs = {"A": {"a"}, "B": {"b"}, "C": {"not c"}, "D": {"b", "not c"}}

    clauses = {c.defn for c in generate_settings_requirements(cfg, channel_reqs, [])}

    # C is disabled, but its state is inverted from the corresponding setting.
    assert clauses == freeze(
        [{("a", False)}, {("b", True)}, {("c", False)}, {("b", True), ("c", False)}]
    )


def test_solve():
    cnf = set(
        [
            CnfClause(defn=frozenset({("a", False)}), comment="A"),
            CnfClause(defn=frozenset({("b", True)}), comment="~B"),
            CnfClause(defn=frozenset({("c", False)}), comment="C"),
            CnfClause(defn=frozenset({("b", True), ("c", False)}), comment="~B or C"),
        ]
    )

    out = solve(cnf)
    assert out == freeze([{("a", True), ("b", False), ("c", True)}])


def test_solve_infeasible():
    cnf = set(
        [
            CnfClause(defn=frozenset({("a", False)}), comment="A"),
            CnfClause(defn=frozenset({("b", True)}), comment="~B"),
            CnfClause(defn=frozenset({("c", True)}), comment="~C"),
            CnfClause(defn=frozenset({("b", False), ("c", False)}), comment="~B or ~C"),  # Conflict
        ]
    )

    try:
        solve(cnf)
        assert False, "Expected infeasibility"
    except SettingsConflictError:
        pass


def test_create_patch_for_asset():
    asset = {
        "foo": False,
        "bar": True,
        "quux": None,
        "baz": {
            "zap": True,
        },
        "unrelated": True,
    }

    # Two possible assignments to the variables above; the top one is more minimal (changes only
    # "bar" vs "quux" and "baz.zap").
    cnf = freeze(
        [
            {("foo", False), ("bar", False), ("quux", False), ("baz.zap", True)},
            {("foo", False), ("bar", True), ("quux", True), ("baz.zap", False)},
        ]
    )
    fieldset, patch = create_patch_for_asset(asset, cnf)

    assert set(fieldset.keys()) == (set(asset.keys()) - {"unrelated", "baz"}) | {
        "baz.zap"
    }
    assert set(patch.keys()) == {"bar"}
