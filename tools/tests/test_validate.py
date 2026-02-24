"""Tests for ACF schema validation.

All test content lives in tools/tests/fixtures/*.acf.
Tests are parametrized so adding a new fixture auto-creates a test case.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from schema.acf_schema import (
    ACTIONS,
    APPROACHES,
    VALID_ACTION_REFS,
    quick_validate,
)

# ── Paths ─────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SEED_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "verified"
PROJECT_ROOT = Path(__file__).parent.parent.parent


def load_fixture(name: str) -> str:
    path = FIXTURES_DIR / f"{name}.acf"
    assert path.exists(), f"Fixture not found: {path}"
    return path.read_text()


def validate_fixture(name: str):
    content = load_fixture(name)
    return quick_validate(f"fixtures/{name}.acf", content)


# ── Fixture discovery ─────────────────────────────────────

VALID_FIXTURES = sorted(p.stem for p in FIXTURES_DIR.glob("valid_*.acf"))
INVALID_FIXTURES = sorted(p.stem for p in FIXTURES_DIR.glob("invalid_*.acf"))
SEED_FILES = sorted(SEED_DATA_DIR.rglob("*.acf")) if SEED_DATA_DIR.exists() else []


# ── Valid fixtures: must all pass ─────────────────────────


@pytest.mark.parametrize("name", VALID_FIXTURES, ids=VALID_FIXTURES)
def test_valid_fixture_passes(name):
    """Every valid_*.acf fixture must pass validation with zero errors."""
    result = validate_fixture(name)
    assert result.ok, f"{name}.acf failed:\n{result}"


@pytest.mark.parametrize("name", VALID_FIXTURES, ids=VALID_FIXTURES)
def test_valid_fixture_strict(name):
    """Every valid_*.acf fixture must also pass strict (no warnings)."""
    result = validate_fixture(name)
    assert result.ok and not result.warnings, (
        f"{name}.acf has warnings in strict mode:\n{result}"
    )


# ── Invalid fixtures: must each trigger the expected rule ─

# fixture stem -> (expected rule, severity)
INVALID_EXPECTED = {
    "invalid_bare_do": ("named_steps", "error"),
    "invalid_bad_approach": ("action_valid", "error"),
    "invalid_missing_fail_target": ("label_exists", "error"),
    "invalid_prob_out_of_range": ("prob_bounded", "error"),
    "invalid_derived_stat": ("no_stored_derived", "error"),
    "invalid_hidden_counter": ("observability", "error"),
    "invalid_unnecessary_quotes": ("minimal_quotes", "warning"),
    "invalid_prob_unbounded": ("prob_bounded", "warning"),
}


@pytest.mark.parametrize(
    "name,expected_rule,severity",
    [
        (name, rule, sev)
        for name, (rule, sev) in INVALID_EXPECTED.items()
    ],
    ids=list(INVALID_EXPECTED.keys()),
)
def test_invalid_fixture_triggers_rule(name, expected_rule, severity):
    """Each invalid_*.acf fixture must trigger its expected validation rule."""
    result = validate_fixture(name)
    if severity == "error":
        triggered = [e.rule for e in result.errors]
        assert expected_rule in triggered, (
            f"{name}.acf should trigger error '{expected_rule}' "
            f"but got errors: {triggered}\nFull result:\n{result}"
        )
    else:
        triggered = [w.rule for w in result.warnings]
        assert expected_rule in triggered, (
            f"{name}.acf should trigger warning '{expected_rule}' "
            f"but got warnings: {triggered}\nFull result:\n{result}"
        )


def test_all_invalid_fixtures_covered():
    """Every invalid_*.acf fixture must have an entry in INVALID_EXPECTED."""
    for name in INVALID_FIXTURES:
        assert name in INVALID_EXPECTED, (
            f"Fixture {name}.acf exists but has no expected rule in INVALID_EXPECTED. "
            f"Add it to the dict."
        )


# ── Seed data: all shipped files must pass ────────────────


@pytest.mark.parametrize(
    "filepath",
    SEED_FILES,
    ids=[str(p.relative_to(SEED_DATA_DIR)) for p in SEED_FILES],
)
def test_seed_data_validates(filepath):
    """All data/verified/*.acf files must pass validation."""
    content = filepath.read_text()
    result = quick_validate(str(filepath), content)
    assert result.ok, f"{filepath}:\n{result}"


@pytest.mark.parametrize(
    "filepath",
    SEED_FILES,
    ids=[str(p.relative_to(SEED_DATA_DIR)) for p in SEED_FILES],
)
def test_seed_data_strict(filepath):
    """All data/verified/*.acf files must pass strict (no warnings)."""
    content = filepath.read_text()
    result = quick_validate(str(filepath), content)
    assert result.ok and not result.warnings, (
        f"{filepath} has warnings in strict mode:\n{result}"
    )


# ── Schema invariants ────────────────────────────────────


def test_action_approach_matrix_complete():
    """The 7x3 matrix must produce exactly 21 valid action refs."""
    assert len(ACTIONS) == 7, f"Expected 7 actions, got {len(ACTIONS)}: {ACTIONS}"
    assert len(APPROACHES) == 3, f"Expected 3 approaches, got {len(APPROACHES)}: {APPROACHES}"
    assert len(VALID_ACTION_REFS) == 21, (
        f"Expected 21 action.approach combos, got {len(VALID_ACTION_REFS)}"
    )


def test_no_careful_approach():
    """Careful is not a valid approach (replaced by Indirect/Structured)."""
    assert "Careful" not in APPROACHES
    for action in ACTIONS:
        assert f"{action}.Careful" not in VALID_ACTION_REFS


# ── CLI tool tests ────────────────────────────────────────


def test_validate_cli_exit_code_zero(fixtures_dir):
    """validate.py returns 0 for valid files."""
    result = subprocess.run(
        [sys.executable, "tools/validate.py", str(fixtures_dir / "valid_rule.acf")],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_validate_cli_exit_code_one(fixtures_dir):
    """validate.py returns 1 for invalid files."""
    result = subprocess.run(
        [sys.executable, "tools/validate.py", str(fixtures_dir / "invalid_bare_do.acf")],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 1, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_validate_cli_strict_mode(fixtures_dir):
    """validate.py --strict returns 1 when there are warnings."""
    result = subprocess.run(
        [
            sys.executable, "tools/validate.py",
            str(fixtures_dir / "invalid_prob_unbounded.acf"),
            "--strict",
        ],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 1, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "WARN" in result.stdout or "FAIL" in result.stdout


def test_validate_cli_verbose_output(fixtures_dir):
    """validate.py output includes file path and summary line."""
    result = subprocess.run(
        [sys.executable, "tools/validate.py", str(fixtures_dir / "valid_plan.acf")],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert "OK" in result.stdout
    assert "Files:" in result.stdout
