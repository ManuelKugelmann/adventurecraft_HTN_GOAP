"""Tests for ACF schema validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from schema.acf_schema import quick_validate


def test_valid_plan():
    content = """plan test.valid [test] {
    method default {
        step_a: do Move.Direct { target = $destination }
        step_b: do Attack.Careful { target = $enemy }
            prob = sigmoid(self.skills.ranged - $enemy.skills.active_defense)
    }
    done { $enemy.health <= 0 }
}"""
    result = quick_validate("test.acf", content)
    assert result.ok, str(result)


def test_bare_do_error():
    content = """plan test.bare [test] {
    method default {
        do Move.Direct { target = $destination }
    }
}"""
    result = quick_validate("test.acf", content)
    assert any(e.rule == "named_steps" for e in result.errors), "Should flag bare do"


def test_invalid_approach():
    content = """plan test.bad_approach [test] {
    method default {
        step_a: do Move.Wrong { target = $destination }
    }
}"""
    result = quick_validate("test.acf", content)
    assert any(e.rule == "action_valid" for e in result.errors), "Should flag invalid approach"


def test_missing_fail_target():
    content = """plan test.bad_ref [test] {
    method default {
        step_a: do Move.Direct { target = $destination }
            fail = NONEXISTENT
    }
}"""
    result = quick_validate("test.acf", content)
    assert any(e.rule == "label_exists" for e in result.errors), "Should flag missing label"


def test_valid_fail_target():
    content = """plan test.good_ref [test] {
    method default {
        step_a: do Move.Direct { target = $destination }
            fail = FALLBACK
        FALLBACK: do Move.Indirect { target = $safehouse }
    }
}"""
    result = quick_validate("test.acf", content)
    assert not any(e.rule == "label_exists" for e in result.errors)


def test_derived_stat_error():
    content = """plan test.derived [test] {
    method default {
        step_a: do Move.Direct { target = $destination }
            prob = sigmoid(self.attributes.authority - 10)
    }
}"""
    result = quick_validate("test.acf", content)
    assert any(e.rule == "no_stored_derived" for e in result.errors), "Should flag stored authority"


def test_prob_out_of_range():
    content = """plan test.prob [test] {
    method default {
        step_a: do Move.Direct { target = $destination }
            prob = 1.5
    }
}"""
    result = quick_validate("test.acf", content)
    assert any(e.rule == "prob_bounded" for e in result.errors), "Should flag prob > 1"


def test_counter_observability():
    content = """plan test.counter [test] {
    method default {
        step_a: do Move.Direct { target = $destination }
    }
    counter threat.test {
        response_a when $enemy.drives.dominance > 50
    }
}"""
    result = quick_validate("test.acf", content)
    assert any(e.rule == "observability" for e in result.errors), "Should flag hidden drives in counter"


def test_unnecessary_quotes_warning():
    content = """plan test.quotes ["test"] {
    method default {
        step_a: do Move.Direct { target = "$destination" }
    }
}"""
    result = quick_validate("test.acf", content)
    assert any(e.rule == "minimal_quotes" for e in result.warnings), "Should warn on unnecessary quotes"


def test_valid_role():
    content = """role farmer [economic, rural] {
    plow: when season == spring, do Modify.Direct { target = $field }, priority = 10
    harvest: when field.crop.ready, do Transfer.Direct { source = $field }, priority = 15
}"""
    result = quick_validate("test.acf", content)
    assert result.ok, str(result)


def test_valid_rule():
    content = """rule fire_spread [physics, L0] {
    spread: when region.fire > 0 AND adjacent.has(Flammable),
            prob = sigmoid(region.fire * 0.01),
            effect: adjacent.fire += 20
}"""
    result = quick_validate("test.acf", content)
    assert result.ok, str(result)


def test_seed_data_validates():
    """All seed data files should pass validation."""
    data_dir = Path(__file__).parent.parent.parent / "data" / "verified"
    for filepath in data_dir.rglob("*.acf"):
        content = filepath.read_text()
        result = quick_validate(str(filepath), content)
        assert result.ok, f"{filepath}: {result}"
