# TBD — Open Questions and Spec Gaps

Items collected from extraction, validation, and design work that need future
discussion or spec extension. Append new entries with the format below.

---

## Format for new entries

```
## [source/context]: [brief description of gap]
**Context:** where/why this came up
**Gap:** what is unclear or missing
**Direction:** suggested resolution
```

---

## extraction-prompts: stale format (when/done/fail vs needs/outcomes)

**Context:** `prompts/extract_plans.md` and `prompts/extract_compounds.md` still
use the old method structure (`when { }`, `done { }`, `fail { }`, `priority = `).

**Gap:** The current spec requires `needs { }` (preconditions) and `outcomes { }`
(postconditions). Several verified seed files (`store_for_winter.acf`,
`investigate.acf`, `cover_tracks.acf`) use the old format because they were
extracted with outdated prompts.

**Direction:** Update all extraction prompts to use `needs { }` / `outcomes { }`.
Migrate existing old-format verified files. Decide whether to grandfather
old-format files or re-extract them.

---

## resolution-functions: no function for simple skill checks (non-contested)

**Context:** `store_for_winter.acf` gather step is a skill check vs a fixed
difficulty (not an adversarial contest). No named resolution function fits cleanly.
Used `resolve_conflict(self.Skills.gathering, 10, 0)` as a placeholder.

**Gap:** `resolve_conflict` is designed for actor-vs-opponent contests. Simple
uncontested skill checks (harvest success, craft success vs fixed recipe difficulty,
travel success vs terrain) have no dedicated function.

**Direction:** Consider `skill_check(actor, skill, difficulty)` or
`craft_chance(actor, difficulty)` accepting a numeric difficulty as second arg
(not just a recipe/entity ref). Or broaden `craft_chance` signature.

---

## extraction-prompts: no prob guidance for rules vs plans

**Context:** Rule files (`detection.acf`, `fire.acf`) use `resolve_conflict()` and
`min()` for probability expressions. Plan files use named resolution functions.
The extraction prompts don't distinguish these contexts.

**Gap:** `extract_rules.md` still lists `sigmoid(x)` as a valid built-in function.
This leads to extracted rules using bare `sigmoid()` instead of `resolve_conflict()`.

**Direction:** Update `extract_rules.md` to list `resolve_conflict()` and
`min()/max()` as the correct forms, and remove `sigmoid()` from the built-in list.
For physics rules (fire spread, decay), `min()` is appropriate. For detection/combat,
use `resolve_conflict()`.

---

## tbd-logging-mechanism: how LLM workflows write to TBD.md

**Context:** Extraction prompts instruct Claude to emit a `_tbd { }` block when
it encounters a spec gap. This file needs a way to collect those blocks.

**Gap:** `tools/extract.py` doesn't parse `_tbd { }` blocks or append to `TBD.md`.
The mechanism is defined but not implemented.

**Direction:** Add a post-processing step in `extract.py` that:
1. Strips any `_tbd { ... }` block from the .acf content before writing the file
2. Appends the block contents (formatted as a TBD entry) to `TBD.md`
This keeps .acf files clean while preserving gap annotations.

---

## secrecy-param: invalid step parameter in verified fixtures

**Context:** `valid_plan.acf` fixture uses `secrecy = 0.9` as an inline action
parameter (`do Move.Indirect { destination = $treeline, secrecy = 0.9 }`).

**Gap:** Per spec, secrecy is an action modifier derived from agent state — NOT a
per-step parameter. Plans declare detection as an outcome using `detection_risk()`.

**Direction:** Remove `secrecy = ` from step params in fixture and in extraction
prompts. Add `secrecy` to the validator's list of disallowed step parameters, or
add a warning. Fix the fixture to use `visible(self, $location), prob = detection_risk(self, $location)` in outcomes.

---
