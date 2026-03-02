"""
ACF schema definitions and validator.
Validates .acf files against the AdventureCraft data spec.

Authoritative spec: https://github.com/ManuelKugelmann/adventurecraft_WIP
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ── Actions & Approaches ──────────────────────
# Three approaches per action: Direct (brute force), Indirect (finesse),
# Structured (systematic/planned). Maps to 21 skills + 2 meta-skills.

ACTIONS = ["Move", "Modify", "Attack", "Defense", "Transfer", "Influence", "Sense"]
APPROACHES = ["Direct", "Indirect", "Structured"]

ACTION_SKILLS = {
    ("Move", "Direct"): "athletics",          # Str+Agi
    ("Move", "Indirect"): "riding",           # Agi+Wit
    ("Move", "Structured"): "travel",         # Wit+Will
    ("Modify", "Direct"): "operate",          # Str+Wit
    ("Modify", "Indirect"): "equipment",      # Agi+Wit
    ("Modify", "Structured"): "crafting",     # Wit+Will
    ("Attack", "Direct"): "melee",            # Str+Agi
    ("Attack", "Indirect"): "ranged",         # Agi+Wit
    ("Attack", "Structured"): "traps",        # Wit+Will
    ("Defense", "Direct"): "active_defense",  # Agi+Str
    ("Defense", "Indirect"): "armor",         # Str+Bod
    ("Defense", "Structured"): "tactics",     # Wit+Will
    ("Transfer", "Direct"): "gathering",      # Str+Agi
    ("Transfer", "Indirect"): "trade",        # Cha+Wit
    ("Transfer", "Structured"): "administration",  # Wit+Will
    ("Influence", "Direct"): "persuasion",    # Cha+Will
    ("Influence", "Indirect"): "deception",   # Cha+Wit
    ("Influence", "Structured"): "intrigue",  # Wit+Will
    ("Sense", "Direct"): "search",            # Agi+Wit
    ("Sense", "Indirect"): "observation",     # Wit+Will
    ("Sense", "Structured"): "research",      # Wit+Spi
}

VALID_ACTION_REFS = {f"{a}.{ap}" for a in ACTIONS for ap in APPROACHES}

# ── Entity Schema (trait-based, see architecture.md) ──

ATTRIBUTES = ["str", "agi", "bod", "wil", "wit", "spi", "cha"]
# authority and reputation are DERIVED from relationships, never stored
DERIVED_ATTRS = ["authority", "reputation"]

SKILLS = list({v for v in ACTION_SKILLS.values()})
META_SKILLS = ["stealth", "awareness"]

DRIVES = ["survival", "luxury", "dominance", "belonging", "knowledge", "lawful", "moral"]

RELATIONSHIP_AXES = ["debt", "reputation", "affection", "familiarity"]

# ── Traits (from unified tree spec) ──────────

SINGLE_TRAITS = [
    "Vitals", "Attributes", "Skills", "Drives", "Agency",
    "Weapon", "Armor", "Perishable", "Flammable", "Edible",
    "Tool", "Container", "Heavy", "Fragile", "Valuable",
    "Stackable", "Material", "LightSource", "Concealed", "Condition",
    "Immaterial", "Spatial", "Climate", "Hydrology", "Lighting",
    "Burning", "Soil", "Populated", "Vehicle",
    "Obscurity", "PlanMeta", "ContractTerms", "AuthStrength",
]

MULTI_TRAITS = [
    "Social", "MemberOf", "DelegatesTo", "KnowsAbout", "Guards",
    "HostileTo", "AlliedWith", "EmployedBy", "ConnectedTo",
    "OwnedBy", "Adjacent", "ActiveRole", "Mirrors", "AuthScope",
    "DelegatedFrom", "NaturalResource", "StatCopy",
]

# ── Elementary effect operations ─────────────

EFFECT_OPS = [
    "Accumulate", "Decay", "Set", "Transfer", "Spread",
    "Create", "Destroy", "AddTrait", "RemoveTrait",
]

# ── Observable state (for counter threat signatures) ──

OBSERVABLE_PATHS = {
    "pos", "location", "weight", "faction", "garrison", "walls",
    "equipped", "action", "building", "terrain", "fire", "water",
    "condition", "visible", "size", "flag", "formation",
    "temperature", "humidity",
}

HIDDEN_PATHS = {
    "drives", "plans", "knowledge", "mood", "skills", "contracts",
    "inventory", "secrets", "fulfillment",
}

# ── Rule layers ───────────────────────────────

class RuleLayer(Enum):
    L0 = 0  # physics (temperature, fire, water, light, terrain)
    L1 = 1  # biology (growth, metabolism, disease, aging, healing)
    L2 = 2  # items (decay, durability, spoilage, fuel)
    L3 = 3  # social (judgment, familiarity, knowledge propagation, mood)
    L4 = 4  # economic (supply/demand, complex interactions, combat)

LAYER_TAGS = {
    "L0": RuleLayer.L0, "L0_Physics": RuleLayer.L0, "physics": RuleLayer.L0,
    "L1": RuleLayer.L1, "L1_Biology": RuleLayer.L1, "biology": RuleLayer.L1,
    "L2": RuleLayer.L2, "L2_Items": RuleLayer.L2, "items": RuleLayer.L2,
    "L3": RuleLayer.L3, "L3_Social": RuleLayer.L3, "social": RuleLayer.L3,
    "L4": RuleLayer.L4, "L4_Economic": RuleLayer.L4, "economic": RuleLayer.L4,
}

# L0 depends on nothing, L1 on L0, L2 on L0, L3 on L0-L2, L4 on L0-L3
LAYER_DEPS = {
    RuleLayer.L0: set(),
    RuleLayer.L1: {RuleLayer.L0},
    RuleLayer.L2: {RuleLayer.L0},
    RuleLayer.L3: {RuleLayer.L0, RuleLayer.L1, RuleLayer.L2},
    RuleLayer.L4: {RuleLayer.L0, RuleLayer.L1, RuleLayer.L2, RuleLayer.L3},
}

# ── Expression functions ──────────────────────

EXPR_FUNCTIONS = {
    "min", "max", "abs", "sigmoid", "prob", "random",
    "count", "any", "sum", "product",
    "distance", "contains", "depth",
    "edge", "co_located", "nearby", "witnessed",
    # Resolution functions (all return 0..1 via internal sigmoid)
    "resolve_conflict",
    "detection_risk", "persuasion_chance", "deception_chance",
    "intimidation_chance", "combat_chance", "lockpick_chance",
    "craft_chance", "observation_chance", "trade_advantage",
    "chase_chance", "identification_risk", "capture_risk",
    "evidence_risk", "attribution_risk",
    # Planning estimate functions (return ActionEstimate struct, not float)
    # Used in needs {} / outcomes {} — often via $var = consider_action(...) binding
    "consider_action", "consider_plan",
    "effective_secrecy_estimate", "drives_permit",
}

# Functions that return structured values (not scalar/float).
# When accessed as $var = f(...), field access $var.field is valid.
# The prob_bounded check must not flag $var.some_prob_field as unbounded.
STRUCTURED_RETURN_FUNCTIONS = {
    "consider_action", "consider_plan",
}

# ── Local variable binding ────────────────────
# $var = expr  inside needs {} / outcomes {} is a local binding.
# $var without = is a plan parameter (must be bound at invocation).
# Regex matches local binding declarations.
RE_LOCAL_BINDING = re.compile(r"^\s*\$(\w+)\s*=\s*(.+)", re.MULTILINE)

# Functions guaranteed to return 0..1 — no wrapping needed.
# Use named resolution functions in all plan/rule data.
# Do NOT use sigmoid() or prob() directly in .acf files.
RESOLUTION_FUNCTIONS = {
    "resolve_conflict",  # generic; use named variants where possible
    "detection_risk", "persuasion_chance", "deception_chance",
    "intimidation_chance", "combat_chance", "lockpick_chance",
    "craft_chance", "observation_chance", "trade_advantage",
    "chase_chance", "identification_risk", "capture_risk",
    "evidence_risk", "attribution_risk",
}

BOUNDED_FUNCTIONS = RESOLUTION_FUNCTIONS  # sigmoid/prob are implementation details, not data API

# ── Validation errors ─────────────────────────

@dataclass
class ValidationError:
    file: str
    path: str  # e.g. "military.siege > assault > BREACH"
    rule: str  # e.g. "action_valid"
    message: str
    severity: str = "error"  # error | warning

@dataclass
class ValidationResult:
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def add(self, err: ValidationError):
        if err.severity == "warning":
            self.warnings.append(err)
        else:
            self.errors.append(err)

    def __str__(self) -> str:
        lines = []
        for e in self.errors:
            lines.append(f"ERROR [{e.rule}] {e.path}: {e.message}")
        for w in self.warnings:
            lines.append(f"WARN  [{w.rule}] {w.path}: {w.message}")
        if self.ok:
            lines.append("OK")
        else:
            lines.append(f"\n{len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        return "\n".join(lines)


# ── Quick regex checks (pre-parser) ──────────

# Matches: name: do Action.Approach { ... }
RE_STEP = re.compile(r"^\s+(\w+):\s+do\s+", re.MULTILINE)

# Matches: do without name prefix (error)
RE_BARE_DO = re.compile(r"^\s+do\s+(?!.*:\s+do)", re.MULTILINE)

# Matches: label: (ALL_CAPS)
RE_LABEL = re.compile(r"^\s+([A-Z][A-Z0-9_]*):\s+do\s+", re.MULTILINE)

# Matches: fail = LABEL
RE_FAIL_REF = re.compile(r"fail\s*=\s*([A-Z][A-Z0-9_]*)")

# Matches: prob = <expr>
RE_PROB = re.compile(r"prob\s*=\s*(.+)")

# Matches: action.approach
RE_ACTION_REF = re.compile(r"do\s+(\w+\.\w+)")

# Matches: _provenance block
RE_PROVENANCE = re.compile(r"_provenance\s*\{")

# Matches: quoted strings (should be minimal)
RE_QUOTED = re.compile(r'"([^"]*)"')

# ── Pre-parser validation ─────────────────────

def quick_validate(filepath: str, content: str) -> ValidationResult:
    """Fast regex-based validation before full parse."""
    result = ValidationResult()

    # Check bare do (missing step name)
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip lines where do is part of a named role rule: "name: when ..., do ..."
        if re.match(r"\w+:\s+when\s+.+,\s*do\s+", stripped):
            continue
        # Skip continuation lines (previous non-empty line ends with comma)
        if stripped.startswith("do "):
            prev_idx = i - 2
            while prev_idx >= 0 and not lines[prev_idx].strip():
                prev_idx -= 1
            if prev_idx >= 0 and lines[prev_idx].rstrip().endswith(","):
                continue
        if stripped.startswith("do ") and not re.match(r"\w+:\s+do\s+", stripped):
            if re.match(r"^\s{4,}do\s+\w+", line):
                result.add(ValidationError(
                    file=filepath, path=f"line {i}",
                    rule="named_steps",
                    message=f"Bare `do` without step name. Add `name: do ...`"
                ))

    # Check action refs are valid
    for m in RE_ACTION_REF.finditer(content):
        ref = m.group(1)
        if ref in VALID_ACTION_REFS:
            continue
        # Could be a qualified plan reference like military.breach_walls — OK
        parts = ref.split(".")
        if parts[0] in ACTIONS and parts[1] not in APPROACHES:
            result.add(ValidationError(
                file=filepath, path=ref,
                rule="action_valid",
                message=f"Invalid approach '{parts[1]}'. Must be Direct|Indirect|Structured"
            ))

    # Check fail references point to existing labels
    labels = {m.group(1) for m in RE_LABEL.finditer(content)}
    for m in RE_FAIL_REF.finditer(content):
        ref = m.group(1)
        if ref not in labels:
            result.add(ValidationError(
                file=filepath, path=ref,
                rule="label_exists",
                message=f"fail target '{ref}' not found. Defined labels: {labels or 'none'}"
            ))

    # Check derived stats aren't referenced as stored
    for attr in DERIVED_ATTRS:
        pattern = re.compile(rf"\.attributes\.{attr}\b|self\.{attr}\b")
        for m in pattern.finditer(content):
            result.add(ValidationError(
                file=filepath, path=m.group(),
                rule="no_stored_derived",
                message=f"'{attr}' is derived from relationships, not stored. Use edge() queries."
            ))

    # Check prob expressions are bounded (heuristic)
    # This check cannot type-verify expressions — it only catches obvious mistakes.
    # Any $var.field access is accepted: variables are user-typed and structured
    # return fields (e.g. ActionEstimate.detection_prob) are known to be 0..1.
    # A real type system would derive boundedness from return types; this heuristic
    # cannot, so widening to accept all $var.field is the correct tradeoff.
    for m in RE_PROB.finditer(content):
        expr = m.group(1).strip()
        # Accept any call to a known bounded function
        if any(f"{fn}(" in expr for fn in BOUNDED_FUNCTIONS):
            continue
        # Accept min()/max() clamps
        if "min(" in expr or "max(" in expr:
            continue
        # Accept any $var.field access — field on any bound variable
        if re.match(r"^\$\w+\.", expr):
            continue
        if re.match(r"^[\d.]+$", expr):
            val = float(expr)
            if not 0 <= val <= 1:
                result.add(ValidationError(
                    file=filepath, path=f"prob = {expr}",
                    rule="prob_bounded",
                    message=f"Probability {val} outside 0..1"
                ))
        else:
            result.add(ValidationError(
                file=filepath, path=f"prob = {expr}",
                rule="prob_bounded",
                message=(
                    "Probability expression should use a named resolution function "
                    "(observation_chance, combat_chance, resolve_conflict, etc.). "
                    "Do not use sigmoid() or prob() directly."
                ),
                severity="warning"
            ))

    # Check observability in counter blocks
    in_counter = False
    in_observe = False
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("counter ") or stripped.startswith("observe {"):
            in_counter = True
            continue
        if in_counter and stripped == "}":
            in_counter = False
            continue
        if in_counter:
            for hidden in HIDDEN_PATHS:
                if f".{hidden}" in stripped or f"${hidden}" in stripped:
                    result.add(ValidationError(
                        file=filepath, path=f"line {i}",
                        rule="observability",
                        message=f"Counter/observe references hidden state '.{hidden}'. Use observable state only."
                    ))

    # Warn on excessive quoting
    quotes = RE_QUOTED.findall(content)
    for q in quotes:
        if " " not in q and not q.startswith("_"):
            result.add(ValidationError(
                file=filepath, path=f'"{q}"',
                rule="minimal_quotes",
                message=f"Unnecessary quotes around '{q}'. Use bare identifier.",
                severity="warning"
            ))

    return result


# ── Coverage matrix ───────────────────────────

def coverage_categories():
    """Returns the matrix dimensions for coverage tracking."""
    return {
        "actions": ACTIONS,
        "approaches": APPROACHES,
        "rule_layers": [l.name for l in RuleLayer],
        "compound_categories": [
            "information", "deception", "social", "economic",
            "political", "protection", "violence",
        ],
        "role_categories": [
            "survival", "economic", "craft", "military",
            "governance", "knowledge", "religious", "social",
            "domestic", "criminal",
        ],
    }
