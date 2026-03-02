# CLAUDE.md -- AdventureCraft HTN-GOAP Dataset

## Authoritative Spec

https://github.com/ManuelKugelmann/adventurecraft_WIP

The WIP repo contains the overarching draft specification. This repo holds the behavior dataset and extraction tooling.

## Project

Public dataset of behavior building blocks for agent-based simulation.
Three data types: `rule`, `role`, `plan`. One expression language. One file format (`.acf`).
Trait-based entity system: everything is a Node with typed trait structs.

## Commands

```bash
# Extract using local claude CLI (subscription auth, no API key needed)
python tools/extract.py --source everyday --batch 5 --local

# Extract using API key (CI/headless)
python tools/extract.py --source everyday --batch 5

# Extract single item
python tools/extract.py --source propp --item absentation --local

# List all available sources
python tools/extract.py --source propp --list-sources

# Dry run (show queue, no calls)
python tools/extract.py --source propp --batch 10 --dry-run

# Validate all data
python tools/validate.py data/

# Validate a single file
python tools/validate.py data/raw/propp/hero_journey.acf

# Generate counter-plans (local)
python tools/counters.py data/verified/ --local

# Coverage report
python tools/coverage.py data/verified/

# Run tests
pytest tools/tests/
```

## Workflow

- Do NOT validate, commit, and push after every small change. Batch changes.
  Only commit at meaningful checkpoints or when explicitly asked.
- Design discussions and iterative edits should accumulate before committing.

## File Format: `.acf`

Three declaration types:

```acf
rule fire_spread [physics, L0] {
    spread: when region.fire > 0 AND adjacent.has(Flammable),
            prob = region.fire * 0.1 * region.wind,
            effect: adjacent.fire += 20
}

role farmer [economic, rural] {
    plow:    when season == spring AND field.state == fallow,
             do Modify.Direct { target = $field }, priority = 10
    harvest: when field.crop.ready,
             do Transfer.Direct { source = $field }, priority = 15
}

plan move_to.walk [movement] {
    needs { $destination.has(Region) AND self.knows(route_to($destination, walking)) }
    outcomes {
        co_located(self, $destination), prob = 0.95
        self.Vitals.Stamina -= distance(self, $destination) * self.Physical.Weight * 0.1
        time += distance(self, $destination) / self.Movement.Speed
    }
    step: do Move.Direct { destination = $destination }
}

plan criminal.heist [criminal, economic] {
    needs { accessible(self, $tools) AND self.knows(layout_of($target_location)) }
    method classic {
        needs { count(self, AlliedWith, willing = true) >= 3 }
        intel:   do acquire_information { about = $vault }
        crack:   do gain_entry { target = $vault_door }
        grab:    do acquire_item { source = $vault }
        escape:  do move_to { destination = $safehouse }
    }
    outcomes {
        accessible(self, $vault.contents), prob = 0.6
        visible(self, $vault.guards), prob = 0.4
        time += 120
    }
}
```

## Quoting Rule

Bare tokens everywhere. Quotes ONLY for human text with spaces.

## Plan Sections

Two sections per plan (and per method):

- `needs { }` — preconditions. Boolean, hard filter. Must be true or method is excluded.
  Checked against agent belief state, not world truth.
- `outcomes { }` — postconditions. Probabilistic. Includes goal, side effects, and costs (including time).
  The planner chains on outcomes and weighs all of them against the agent's drives.

Top-level plans compose sub-plans. Leaf plans contain concrete `do Action.Approach` steps.
Methods may mix sub-plan references and concrete actions.
The planner auto-inserts sub-plans when `needs` are unmet (e.g. missing item, missing knowledge, missing access).

## Expression Language

Trait field paths: `Vitals.Health`, `entity.path`
Built-in functions: see `schema/utility_functions.acf` for full catalog
Core functions: `distance(A, B)`, `accessible(self, node)`, `co_located(a, b)`, `visible(a, b)`, `self.knows(X)`
Planning functions: `consider_action(self, Action.Approach, target)`, `consider_plan(self, method)`
Math: `sigmoid(x)`, `min()`, `max()`, `abs()`, `count()`, `sum()`
Operators: `+ - * / < > == != >= <= AND OR NOT`

### Local variable bindings

`$var = expr` inside `needs {}` or `outcomes {}` binds a local variable.
Use when a structured-return function result is accessed on multiple fields — call once, read many:

```acf
needs {
    $est = consider_action(self, Move.Direct, $dest),
    $est.detection_prob < 0.15 AND $est.costs.stamina < self.Vitals.Stamina
}
```

Scoping rules:
- A `$name` with `= expr` in the block is a **local** (computed once in scope)
- A `$name` without `= expr` is a **plan parameter** (must be bound at invocation)
- Local bindings do not cross block boundaries (`needs` locals invisible in `outcomes`)
- Bindings must be declared before use within the same block

## Validation Rules

1. All expressions resolve to valid terminals
2. `do` uses valid Action x Approach (7x3 table)
3. Decomposition depth <= 6
4. Every step has a name
5. `prob` bounded 0..1
6. Counter observables: only externally visible state
7. No stored authority/reputation (derived from relationships)
8. No circular references
9. All `$param` references have matching definitions

## Actions (7x3)

```
Action     Direct           Indirect         Structured
Move       athletics        riding           travel
Modify     operate          equipment        crafting
Attack     melee            ranged           traps
Defense    active_defense   armor            tactics
Transfer   gathering        trade            administration
Influence  persuasion       deception        intrigue
Sense      search           observation      research
```

## Elementary Effect Ops

Accumulate, Decay, Set, Transfer, Spread, Create, Destroy, AddTrait, RemoveTrait

## Rule Layers

L0 (Physics) -> L1 (Biology) -> L2 (Items) -> L3 (Social) -> L4 (Economic)

## Directory Layout

```
data/
  raw/           LLM-extracted, unverified
  verified/      human-reviewed, ships with game
  stats/         runtime sidecars, gitignored
prompts/         extraction prompts per data type
tools/           Python extraction/validation/coverage
schema/          expression grammar, entity schema
docs/            spec, summary, source catalog
.github/workflows/  CI/CD automation
```

## Extraction Workflow

1. `tools/extract.py` calls Claude API with source text + prompt
2. Claude returns `.acf` content
3. `tools/validate.py` checks it
4. If valid -> PR to `data/raw/<source>/`
5. Human reviews -> merges to `data/verified/`
6. `tools/counters.py` generates counter-plans for new entries

## When Editing

- Every `do` line MUST have a `name:` prefix
- ALL_CAPS labels only when referenced by `fail =`
- Tags are bare identifiers in `[]`, no quotes
- `_provenance { }` section on every extracted file
- `rate` and `prob` are mutually exclusive on rules
- Rules respect layer dependencies: L0->L1->L2->L3->L4
- Approaches are Direct, Indirect, Structured (NOT Careful)
- Authority/reputation derived from relationships, never stored as attributes
- Plans use `needs` (preconditions) and `outcomes` (postconditions), NOT `precond`, `done`, or `estimates`
- `needs` are boolean hard filters checked against agent belief state
- `outcomes` are probabilistic and include goal, side effects, and costs (including `time +=`)
- Top-level plans compose sub-plans; leaves have concrete `do` steps; methods may mix both
- Utility functions cataloged in `schema/utility_functions.acf`
- World rules cataloged in `schema/world_rules.acf`
- Resolution functions cataloged in `schema/utility_functions.acf` under RESOLUTION category

## Data Creation Guidelines

### Composition hierarchy

- **Composite plans** (high-level) reference ONLY sub-plans. No concrete `do Action.Approach` steps.
  If there are multiple ways to accomplish a step, it MUST be a sub-plan reference.
- **Leaf plans** contain concrete `do Action.Approach` steps. These are the bottom of the tree.
- **Methods** may mix sub-plan references and concrete actions when some steps have exactly
  one approach and others have multiple approaches.
- Build from BOTH directions: top-down (decompose goals into sub-plans) and bottom-up
  (build reusable leaf plans for common problems).

### Secrecy and action modifiers

- Secrecy is an action modifier that flows from agent state, NOT a per-step parameter.
  Do NOT write `do Move.Direct { destination = X, secrecy = 0.9 }`.
- The engine applies secrecy as a modifier to all actions based on the agent's current
  stealth skill, equipment, situation (lighting, concealment, noise).
- Plans declare detection as an outcome: `visible(self, X), prob = detection_risk(self, X)`.
  The engine resolves the actual probability.

### Resolution functions for contested actions

- ALL adversarial/contested outcomes MUST use a named resolution function, not inlined sigmoids.
- Resolution functions follow the pattern: `sigmoid(actor_strength - opponent_strength + situational)`.
- Two contexts:
  - **ESTIMATE**: planner uses agent belief state (may be wrong → plan failure at runtime).
  - **SIMULATE**: engine uses world truth for actual outcome.
- Core resolution functions (see `schema/utility_functions.acf`):
  - `detection_risk(actor, observers)` — stealth vs observation
  - `persuasion_chance(actor, target)` — honest social influence
  - `deception_chance(actor, target)` — lying, manipulation
  - `intimidation_chance(actor, target)` — threats, coercion
  - `combat_chance(attacker, defender)` — attack vs defense
  - `lockpick_chance(actor, lock)` — lock defeat
  - `craft_chance(actor, recipe)` — crafting, forging, repairing
  - `observation_chance(actor, target)` — noticing, learning
  - `trade_advantage(buyer, seller)` — price negotiation
  - `chase_chance(runner, pursuer)` — escape vs pursuit

### Plan library coverage

- Prioritize diverse everyday plans that the planner auto-inserts when drives are violated:
  `rest`, `eat`, `drink`, `find_shelter`, `tend_wound`, `flee_danger`, etc.
- Build reusable building blocks that compose into many higher-level plans:
  `move_to`, `acquire_access`, `acquire_information`, `acquire_item`, `gain_entry`,
  `influence_person`, `neutralize_security`, `cover_tracks`, `establish_cover`.
- Each building block should have multiple methods covering different approaches.
- Think about common problems and derive different plans for each:
  "How does an agent get somewhere?" → walk, ride, sail, sneak
  "How does an agent learn something?" → ask, observe, research, bribe, explore

### Counters and adversary prediction

- Counter blocks on plans are **cached predictions** — precomputed "standard response"
  to observable threat signatures. Fast lookup for the planner.
- Counters are **bidirectional**: offense counters defense, defense counters offense.
  `secure_vault` has counters for heist patterns. `criminal.heist` has counters for
  vault security. Each references the opposing plan by ID.
- Counter conditions ONLY reference observable state (pos, weight, faction, garrison,
  walls, equipped, visible actions, terrain). NEVER: drives, plans, knowledge, mood, skills.
- Counters are NOT the only way adversaries respond. They cover archetypal patterns.
  Agents with deeper knowledge can predict novel responses beyond the catalog.
- Three tiers: Tier 0 (counter lookup, O(1)), Tier 1 (role-based prediction, depth 1),
  Tier 2 (adversary plan simulation, depth 2). Simple agents stop at Tier 0.
- Tier 1+ agents read the adversary's counter blocks to see what they expect,
  then deliberately subvert it. The backreference enables strategic reasoning.
- Adversary behavioral responses (guard raises alarm, authority investigates) are NOT
  world rules. They are role-driven decisions. The planner predicts them from knowledge
  of the adversary's role and drives.
- Evidence is just items with Physical + Decayable traits. No special forensics system.
- Authorities/laws/mob = implicit contracts. A warrant is Influence.Structured.
- Inception depth limit: max 2 levels. No infinite regress.

### Worldmodel

- Each agent has a **worldmodel** = filtered ground truth + stored overrides.
  No duplication of ground truth. Only overrides are stored.
- **Base layer** (live query, no storage): complete world state + sim history,
  filtered by the agent's senses, alertness, memory, co-location, detection_risk,
  and time decay. `self.knows(fact)` queries this filtered view.
- **Deterministic replay**: sim is deterministic, so full history doesn't need
  storage — only sparse keyframes. Any interval reconstructs by replaying from
  the nearest keyframe with the agent's perception filter applied. Save game =
  keyframe + thin override layer.
- **Override layer** (stored): second-hand information (someone told me),
  deductions (suspect plan conclusions), corrections to stale perception.
  Overrides take priority over the filtered base when both exist.
- `performed($subject, action_type, params)` queries sim history for observed actions.
  The action exists in ground truth; `self.knows(performed(...))` returns true only if
  the agent's perception filter passes for that event.
- **Override storage strategy — reference, don't copy.** If belief matches GT,
  store a reference (pointer + confidence meta). If belief diverges (lied to,
  wrong deduction, outdated), store a divergent value with accuracy meta.
- **Node models are overrides.** `self.worldmodel($node)` accesses the agent's
  override model of another node. These models mirror node structure: active plans,
  roles, traits. When a guard's suspect plan concludes, it writes an override:
  `self.worldmodel($subject).active_plan = criminal.heist` — the guard's best
  reconstruction. The thief has the real plan (ground truth). The guard has a
  truncated/wrong/generic version (override). Mismatch = wrong prediction.
  This IS the ESTIMATE/SIMULATE split.
- Expression syntax: `self.knows(X)` uses the same query syntax as world state
  queries, just targeting the agent's worldmodel instead of ground truth.
  No separate "knowledge query language." `self.worldmodel($node)` for
  structured access to override entries. Both query the same worldmodel.
- `suspected($subject, plan_id)` is a knowledge fact created when a suspect plan
  reports to authority. Authorities receiving this may activate investigation behaviors.

### Suspect plans and plan recognition

- Plan detection uses **suspect plans** (`suspect.*`). The active plan IS the suspicion.
  No separate belief flags — running `suspect.heist` = actively investigating.
- Alertness/defensiveness regularly triggers the planner to consider suspect plans
  against various threats each tick. Guards don't wait for specific suspicious actions —
  their alertness drive proactively evaluates suspect plan methods against recent
  perceptions in the worldmodel base layer. Higher alertness = more budget for suspicion.
- Suspect plans are regular plans with `needs` that check sim history (filtered) and
  `outcomes` that write worldmodel overrides: `self.worldmodel($subject).active_plan = ...`
- The active suspect plan is a **virtual item** on the executing agent — observable.
  A thief can see the guard has shifted from routine patrol to focused investigation.
  When the plan completes or dismisses, suspicion lifts naturally.
- Base suspect plans: `suspect.theft` (heist, burglary, pickpocket, con patterns),
  `suspect.smuggling`, `suspect.hostile_approach`. Any trained guard can use.
- Specialized suspect plans: `suspect.heist` (distinguishes heist methods),
  `suspect.ambush` (route-specific ambush analysis). Requires domain training.
- Planning budget per tick limits suspect plan depth. Simple agents can't afford
  deep suspect plans. Smart agents run specialized variants. Budget = intelligence.

### Guard variants and role-driven detection

- Guard roles are specialized by post. Each variant inherits base guard behaviors
  (patrol, alert, defend, arrest, report) and adds:
  **Observe** (Sense actions feed sim history perception) →
  **Suspect** (trigger suspect.* plan — the active plan IS the suspicion) →
  **Escalate** (suspect plan outcomes report to authority, trigger defense).
- `vault_guard` runs `suspect.heist` to distinguish heist methods.
  `gate_guard` runs `suspect.smuggling` for contraband patterns.
  `market_guard` runs `suspect.theft` for pickpocket/shoplifting.
  `caravan_guard` runs `suspect.ambush` for ambush patterns.
- A guard who hasn't been trained (doesn't know the suspect plan) can't recognize
  the pattern. A farmer witnessing the same actions as a vault guard won't investigate
  — they don't have the suspect plan in their repertoire.

### World rules

- Every adversarial interaction needs a predictable resolution mechanism.
- Rules are cataloged in `schema/world_rules.acf` with implementation status.
- Categories: PHYSICS (L0), BIOLOGY (L1), DETECTION (L3), COMBAT (L3), SOCIAL (L3), ECONOMIC (L4).
- World rules are physics/perception — things that HAPPEN regardless of intent
  (fire spreads, evidence decays, detection resolves). NOT adversary choices.
- Adversary choices (raise alarm, investigate, pursue) are role behaviors, not world rules.
