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
Math: `sigmoid(x)`, `min()`, `max()`, `abs()`, `count()`, `sum()`
Operators: `+ - * / < > == != >= <= AND OR NOT`

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

### World rules

- Every adversarial interaction needs a predictable resolution mechanism.
- Rules are cataloged in `schema/world_rules.acf` with implementation status.
- Categories: PHYSICS (L0), BIOLOGY (L1), DETECTION (L3), COMBAT (L3), SOCIAL (L3), ECONOMIC (L4).
