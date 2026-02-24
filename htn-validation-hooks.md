# HTN Dataset — Validation & Hooks

## Architecture

```
Author (human or LLM)
    │
    ▼
 raw .yaml file
    │
    ├──→ schema_check        (structure)
    ├──→ expr_lint            (expression grammar)
    ├──→ grounding_check      (all refs resolve to real state)
    ├──→ observability_check  (threats only see visible state)
    ├──→ decomposition_check  (tasks reach ActionCalls within depth)
    ├──→ counter_depth_check  (chains terminate ≤ 4)
    ├──→ allocation_check     (fractional sums valid)
    ├──→ stats_check          (tracked fields are computable)
    │
    ▼
 verified/ or error report
```

All checks are independent. Run all, report all errors. No short-circuit.

---

## Expression Linter

Parses every `Expression` field and validates against the grammar.

```python
# scripts/validate/expr_lint.py

VALID_TERMINALS = {
    "STAT": {
        "attributes": {"str", "agi", "bod", "wil", "int", "spi", "cha"},
        "skills": {
            "athletics", "riding", "travel",
            "operate", "equipment", "crafting",
            "melee", "ranged", "traps",
            "active_defense", "armor", "tactics",
            "gathering", "trade", "administration",
            "persuasion", "deception", "intrigue",
            "search", "observation", "research",
            "stealth", "awareness",
        },
        "drives": {"survival", "luxury", "dominance", "belonging", "knowledge", "lawful", "moral"},
        "weight": None,  # scalar
        "pos": None,
        "health": None,
        "supplies": None,
        "mood": None,
        "inventory": "*",  # any sub-key
        "modifier": {"stealth", "awareness"},
    },
    "EDGE": {
        "types": {
            "social", "member_of", "owns", "holds", "contains",
            "located_in", "connected_to", "adjacent", "employed_by",
            "delegates_to", "parent_template", "supplies",
            "hostile_to", "allied_with", "guards", "knows_about", "parent_of",
        },
        "social_fields": {"debt", "reputation", "affection", "familiarity"},
        "agg_modes": {"exists", "min_depth", "sum", "min", "max", "product"},
    },
}

VALID_OPERATORS = {"+", "-", "*", "/", "<", ">", "==", "!=", ">=", "<=", "AND", "OR", "NOT"}
VALID_FUNCTIONS = {"min", "max", "abs", "sigmoid", "count", "any", "sum", "product", "prob", "random"}
VALID_SUGAR = {"HAS", "AT", "ALIVE", "CONTROLS", "CONNECTED"}

ACTIONS = {"Move", "Modify", "Attack", "Defense", "Transfer", "Influence", "Sense"}
APPROACHES = {"Direct", "Careful", "Indirect"}

EFFECTS = {"SET", "ADD", "REMOVE", "CREATE", "DESTROY", "ADD_EDGE", "REMOVE_EDGE"}


class ExprError:
    def __init__(self, path: str, field: str, expr: str, message: str):
        self.path = path
        self.field = field
        self.expr = expr
        self.message = message

    def __str__(self):
        return f"{self.path}:{self.field} — {self.message}\n  expr: {self.expr}"


def lint_expr(expr: str, context: str, path: str, field: str) -> list[ExprError]:
    """
    Validate a single expression string.
    context: "precondition" | "effect" | "probability" | "cost" | "observable"
    """
    errors = []

    # 1. Tokenize and check all identifiers resolve
    tokens = tokenize(expr)
    for tok in tokens:
        if tok.type == "IDENTIFIER":
            err = validate_identifier(tok.value, context)
            if err:
                errors.append(ExprError(path, field, expr, err))

    # 2. Context-specific rules
    if context == "observable":
        # Threat signatures can ONLY reference externally visible state
        for tok in tokens:
            if tok.type == "IDENTIFIER":
                if references_internal_state(tok.value):
                    errors.append(ExprError(path, field, expr,
                        f"Observable references internal state: {tok.value}. "
                        f"ThreatSignatures can only see: pos, weight, visible_actions, "
                        f"faction, equipped items, building state. "
                        f"NOT: drives, plans, knowledge, mood, skills (unless demonstrated)."))

    if context == "effect":
        # Effects must use valid effect operators
        if not any(expr.startswith(op) or f".{op.lower()}" in expr.lower() for op in EFFECTS):
            # Allow mutation syntax: entity.path += expr
            if not any(op in expr for op in ["+=", "-=", "=", "=> destroy", "=> create"]):
                errors.append(ExprError(path, field, expr,
                    "Effect must use SET/ADD/REMOVE/CREATE/DESTROY/ADD_EDGE/REMOVE_EDGE or mutation syntax"))

    if context == "probability":
        # Must evaluate to 0..1
        if "sigmoid" not in expr and "prob" not in expr and "min(1" not in expr:
            # Heuristic: warn if no bounding function
            errors.append(ExprError(path, field, expr,
                "WARNING: probability expression has no bounding function (sigmoid/prob/min). "
                "May produce values outside 0..1."))

    # 3. No derived-stat references
    DERIVED_STATS = {"authority", "reputation"}
    for tok in tokens:
        if tok.type == "IDENTIFIER" and any(d in tok.value.lower() for d in DERIVED_STATS):
            # Allow edge(...).reputation (that's the relationship axis)
            if "edge(" not in expr and "social" not in expr:
                errors.append(ExprError(path, field, expr,
                    f"References derived stat '{tok.value}'. "
                    f"Authority/Reputation are derived from relationships. "
                    f"Use edge(a, b, social).reputation or compute from debt/affection/familiarity."))

    return errors


INTERNAL_STATE = {"drives", "plans", "knowledge", "mood", "skills", "plan_confidence"}

def references_internal_state(identifier: str) -> bool:
    parts = identifier.split(".")
    return any(p in INTERNAL_STATE for p in parts)
```

---

## Grounding Check

Every entity/path reference must resolve to something that exists in the game schema.

```python
# scripts/validate/grounding_check.py

ENTITY_SCHEMA = {
    "attributes": {"str", "agi", "bod", "wil", "int", "spi", "cha"},
    "skills": set(VALID_TERMINALS["STAT"]["skills"]),
    "drives": set(VALID_TERMINALS["STAT"]["drives"]),
    "weight": "int",
    "pos": "vec2",
    "health": "float",
    "supplies": "float",
    "mood": "float",
    "inventory": "dict[str, int]",
    "modifier": {"stealth": "float", "awareness": "float"},
    "garrison": "int",           # settlement-specific
    "walls": {"condition": "float", "height": "float"},
    "faction": "string",
}

REGION_SCHEMA = {
    "temperature": "float",
    "humidity": "float",
    "water": "float",
    "threat_level": "float",
    "population": "int",
    "capacity": "int",
    "weather": "enum",
    "terrain": "enum",
    "fire": "float",
}

OBJECT_SCHEMA = {
    "condition": "float",
    "weight": "float",
    "value": "float",
    "type": "string",
    "equipped": "bool",
    "in_use": "bool",
}


def check_grounding(expr: str, path: str, field: str) -> list[ExprError]:
    """Verify every dotted path resolves to a known schema field."""
    errors = []
    for ref in extract_dot_paths(expr):
        root, *parts = ref.split(".")
        if root in ("actor", "self", "target", "attacking_force", "defending_force"):
            schema = ENTITY_SCHEMA
        elif root == "region":
            schema = REGION_SCHEMA
        elif root in ("item", "object"):
            schema = OBJECT_SCHEMA
        elif root.startswith("$"):
            continue  # parameter — checked separately
        else:
            continue  # could be a bound variable from count/any

        current = schema
        for part in parts:
            if current == "*":
                break  # wildcard accepts anything
            if isinstance(current, dict):
                if part not in current:
                    errors.append(ExprError(path, field, expr,
                        f"Unknown path: {ref}. '{part}' not in schema. "
                        f"Valid: {sorted(current.keys()) if isinstance(current, dict) else current}"))
                    break
                current = current[part]
            elif isinstance(current, set):
                if part not in current:
                    errors.append(ExprError(path, field, expr,
                        f"Unknown value: {ref}. '{part}' not in {sorted(current)}"))
                break
            else:
                break  # scalar — no further nesting
    return errors
```

---

## ActionCall Validator

```python
# scripts/validate/action_check.py

ACTION_SKILL_MAP = {
    ("Move", "Direct"): "athletics",
    ("Move", "Careful"): "riding",
    ("Move", "Indirect"): "travel",
    ("Modify", "Direct"): "operate",
    ("Modify", "Careful"): "equipment",
    ("Modify", "Indirect"): "crafting",
    ("Attack", "Direct"): "melee",
    ("Attack", "Careful"): "ranged",
    ("Attack", "Indirect"): "traps",
    ("Defense", "Direct"): "active_defense",
    ("Defense", "Careful"): "armor",
    ("Defense", "Indirect"): "tactics",
    ("Transfer", "Direct"): "gathering",
    ("Transfer", "Careful"): "trade",
    ("Transfer", "Indirect"): "administration",
    ("Influence", "Direct"): "persuasion",
    ("Influence", "Careful"): "deception",
    ("Influence", "Indirect"): "intrigue",
    ("Sense", "Direct"): "search",
    ("Sense", "Careful"): "observation",
    ("Sense", "Indirect"): "research",
}

def check_action_call(action_call: dict, path: str) -> list[str]:
    errors = []
    action = action_call.get("action")
    approach = action_call.get("approach")

    if action not in ACTIONS:
        errors.append(f"{path}: invalid action '{action}'. Valid: {sorted(ACTIONS)}")

    if approach not in APPROACHES:
        errors.append(f"{path}: invalid approach '{approach}'. Valid: {sorted(APPROACHES)}")

    if (action, approach) in ACTION_SKILL_MAP:
        expected_skill = ACTION_SKILL_MAP[(action, approach)]
        declared_skill = action_call.get("skill")
        if declared_skill and declared_skill != expected_skill:
            errors.append(f"{path}: action {action}/{approach} implies skill '{expected_skill}', "
                          f"but declared '{declared_skill}'")

    intensity = action_call.get("params", {}).get("intensity")
    secrecy = action_call.get("params", {}).get("secrecy")
    if intensity is not None and isinstance(intensity, (int, float)):
        if not 0.0 <= intensity <= 1.0:
            errors.append(f"{path}: intensity {intensity} outside 0..1")
    if secrecy is not None and isinstance(secrecy, (int, float)):
        if not 0.0 <= secrecy <= 1.0:
            errors.append(f"{path}: secrecy {secrecy} outside 0..1")

    return errors
```

---

## Structural Checks

```python
# scripts/validate/structure_check.py

def check_decomposition_depth(task: dict, registry: dict, max_depth=6, current_depth=0) -> list[str]:
    """Every Task must reach ActionCalls within max_depth."""
    if current_depth > max_depth:
        return [f"Task '{task['id']}' exceeds max decomposition depth {max_depth}"]

    errors = []
    for method in task.get("methods", []):
        for subtask_ref in method.get("subtasks", []):
            ref_id = subtask_ref.get("ref")
            resolved = registry.get(ref_id)
            if resolved is None:
                errors.append(f"Task '{task['id']}' method '{method['id']}': "
                              f"unresolved ref '{ref_id}'")
            elif is_action_call(resolved):
                continue  # leaf — OK
            else:
                errors.extend(check_decomposition_depth(resolved, registry, max_depth, current_depth + 1))
    return errors


def check_counter_depth(counter_id: str, registry: dict, max_depth=4, visited=None) -> list[str]:
    """Counter chains must terminate within max_depth."""
    if visited is None:
        visited = set()
    if counter_id in visited:
        return [f"Circular counter chain detected: {counter_id} already in {visited}"]
    if len(visited) >= max_depth:
        return [f"Counter chain exceeds depth {max_depth}: {' → '.join(visited)} → {counter_id}"]

    visited = visited | {counter_id}
    errors = []
    task = registry.get(counter_id)
    if task and "counters" in task:
        for response in task["counters"].get("responses", []):
            errors.extend(check_counter_depth(response["ref"], registry, max_depth, visited))
    return errors


def check_allocation(group_exec: dict) -> list[str]:
    """Fractional allocations must be valid."""
    errors = []
    total = sum(p.get("allocation", 0) for p in group_exec.get("active_plans", []))
    if total > 1.0 + 1e-6:
        errors.append(f"Total allocation {total:.3f} > 1.0")

    for plan in group_exec.get("active_plans", []):
        mix_total = sum(plan.get("action_mix", {}).values())
        if abs(mix_total - 1.0) > 1e-6:
            errors.append(f"Plan '{plan.get('plan')}' action_mix sums to {mix_total:.3f}, not 1.0")

        if plan.get("allocation", 0) < 0.05:
            errors.append(f"Plan '{plan.get('plan')}' allocation {plan['allocation']} below min 0.05")

    if len(group_exec.get("active_plans", [])) > 4:
        errors.append(f"Concurrent plans {len(group_exec['active_plans'])} exceeds max 4")

    return errors
```

---

## Observability Fence

The hardest rule to enforce — and the most important.

```python
# scripts/validate/observability_check.py

# State that is externally observable (Sense action can detect)
OBSERVABLE_STATE = {
    "pos", "weight", "faction", "location",
    "garrison", "walls", "walls.condition", "walls.height",
    "equipped",                     # what they're carrying visibly
    "supplies",                     # approximate, from caravan size
    "health",                       # rough, from visible wounds
    "action",                       # current visible action (not plan, just the action)
    "building", "structure",        # built things are visible
    "terrain", "weather",           # environment
}

# State that requires infiltration / specific knowledge
HIDDEN_STATE = {
    "drives",                       # internal motivation
    "plans", "active_plans",        # intentions
    "knowledge", "knows_about",     # what they know
    "mood",                         # internal state
    "skills",                       # unless demonstrated
    "plan_confidence",              # meta-planning
    "inventory",                    # hidden items
    "contracts",                    # private agreements
    "modifier.stealth",            # by definition hidden
}


def check_threat_observables(threat: dict, path: str) -> list[str]:
    errors = []
    for i, obs_expr in enumerate(threat.get("observables", [])):
        refs = extract_dot_paths(obs_expr)
        for ref in refs:
            parts = ref.split(".")
            # Skip self-references (observer can see own state)
            if parts[0] in ("self", "observer"):
                continue
            # Check if any part references hidden state
            for j, part in enumerate(parts):
                if part in HIDDEN_STATE:
                    errors.append(
                        f"{path}.observables[{i}]: references hidden state '{'.'.join(parts[:j+1])}'. "
                        f"ThreatSignatures can only observe: {sorted(OBSERVABLE_STATE)}. "
                        f"To detect hidden state, require a prior Sense action with sufficient skill."
                    )
                    break
    return errors
```

---

## Post-Edit Hook

Git pre-commit hook that runs all validators on changed `.yaml` files.

```bash
#!/bin/bash
# .git/hooks/pre-commit

CHANGED=$(git diff --cached --name-only --diff-filter=ACM | grep '\.yaml$')
if [ -z "$CHANGED" ]; then
    exit 0
fi

ERRORS=0

for file in $CHANGED; do
    echo "Validating: $file"

    # 1. YAML syntax
    python -c "import yaml; yaml.safe_load(open('$file'))" 2>&1
    if [ $? -ne 0 ]; then
        echo "  FAIL: invalid YAML"
        ERRORS=$((ERRORS + 1))
        continue
    fi

    # 2. JSON Schema
    python scripts/validate/schema_check.py "$file"
    ERRORS=$((ERRORS + $?))

    # 3. Expression lint
    python scripts/validate/expr_lint.py "$file"
    ERRORS=$((ERRORS + $?))

    # 4. Grounding
    python scripts/validate/grounding_check.py "$file"
    ERRORS=$((ERRORS + $?))

    # 5. Observability (only for counter/threat files)
    if echo "$file" | grep -q "counter\|threat"; then
        python scripts/validate/observability_check.py "$file"
        ERRORS=$((ERRORS + $?))
    fi
done

# 6. Cross-file checks (need full registry)
if [ $ERRORS -eq 0 ]; then
    python scripts/validate/decomposition_check.py --changed $CHANGED
    ERRORS=$((ERRORS + $?))

    python scripts/validate/counter_depth_check.py --changed $CHANGED
    ERRORS=$((ERRORS + $?))
fi

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "BLOCKED: $ERRORS validation error(s). Fix before committing."
    exit 1
fi

echo "All checks passed."
exit 0
```

---

## Claude Code Integration

Claude (as author) runs the same validators inline during generation.

```yaml
# prompts/system_hook.md — prepended to every LLM extraction prompt

After generating YAML output, self-check:

1. Every Expression uses only these terminals:
   - entity.{attributes,skills,drives,weight,pos,health,supplies,mood,inventory,modifier}
   - edge(from, to, {type}).{debt,reputation,affection,familiarity}
   - region.{temperature,humidity,water,threat_level,population,capacity,weather,terrain,fire}
   - object.{condition,weight,value,type,equipped,in_use}
   - $param references

2. Every ActionCall uses valid action×approach from:
   Move×{Direct,Careful,Indirect}, Modify×{...}, Attack×{...},
   Defense×{...}, Transfer×{...}, Influence×{...}, Sense×{...}

3. ThreatSignature.observables reference ONLY:
   pos, weight, faction, garrison, walls, equipped, action, building, terrain
   NEVER: drives, plans, knowledge, mood, skills, contracts

4. Probability expressions are bounded 0..1 (use sigmoid or min/max)

5. No references to Authority or Reputation as stored stats
   (use edge(a,b,social).reputation or derive from debt/affection)

6. Counter chains: if this task has counters, verify no circular refs

If any check fails, fix the output before presenting it.
```

### Claude Code Post-Generate Script

```bash
#!/bin/bash
# scripts/claude_post_generate.sh
# Run after Claude generates any .yaml file

FILE=$1

echo "=== Post-generate validation: $FILE ==="

python scripts/validate/schema_check.py "$FILE" || exit 1
python scripts/validate/expr_lint.py "$FILE" || exit 1
python scripts/validate/grounding_check.py "$FILE" || exit 1

if echo "$FILE" | grep -q "counter\|threat"; then
    python scripts/validate/observability_check.py "$FILE" || exit 1
fi

echo "=== PASS ==="
```

---

## CI Pipeline

```yaml
# .github/workflows/validate.yml

name: Validate HTN Dataset
on:
  pull_request:
    paths: ['data/**', 'schema/**']

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install pyyaml jsonschema

      - name: Schema check
        run: python scripts/validate/schema_check.py data/

      - name: Expression lint
        run: python scripts/validate/expr_lint.py data/

      - name: Grounding check
        run: python scripts/validate/grounding_check.py data/

      - name: Observability fence
        run: python scripts/validate/observability_check.py data/counters/

      - name: Decomposition depth
        run: python scripts/validate/decomposition_check.py data/

      - name: Counter chain depth
        run: python scripts/validate/counter_depth_check.py data/counters/

      - name: Allocation validity
        run: python scripts/validate/allocation_check.py data/

      - name: Coverage report
        run: python scripts/analyze/coverage_report.py data/ --output coverage.md

      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with: { name: coverage, path: coverage.md }
```

---

## Error Messages

Every error must be actionable. Pattern:

```
{file}:{field} — {what's wrong}
  expr: {the actual expression}
  expected: {what it should look like}
  hint: {how to fix it}
```

Examples:
```
data/raw/tvtropes/siege.yaml:methods[0].preconditions[1]
  — References hidden state 'target.drives.survival'
  expr: target.drives.survival < 30
  expected: observable state only (pos, weight, faction, garrison, walls, ...)
  hint: Replace with observable proxy, e.g. 'target.garrison < target.walls.capacity * 0.3'

data/raw/military/raid.yaml:steps[2].probability
  — Probability expression unbounded
  expr: actor.skills.melee - target.defense
  expected: value in 0..1
  hint: Wrap in sigmoid(): sigmoid(actor.skills.melee - target.defense)

data/raw/ck3/alliance.yaml:counters.responses[0].ref
  — Unresolved template ref 'political.assassinate_leader'
  expected: existing template ID in registry
  hint: Check data/verified/political/ or create the missing template
```
