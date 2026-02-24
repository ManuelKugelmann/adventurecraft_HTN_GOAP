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

plan criminal.heist [criminal, economic] {
    method classic {
        when { crew.weight >= 3 }
        recon:   do Sense.Structured { target = $vault, secrecy = 0.8 }
        CRACK:   do Modify.Direct { target = $vault_door }
            prob = sigmoid(crew.skills.crafting - $vault.security)
            fail = ABORT
        grab:    do Transfer.Direct { source = $vault, secrecy = 0.9 }
        ABORT:   do Move.Structured { destination = $safehouse, secrecy = 0.9 }
    }
    done { self.inventory.value > $vault.former_value * 0.5 }
}
```

## Quoting Rule

Bare tokens everywhere. Quotes ONLY for human text with spaces.

## Expression Language

Trait field paths: `Vitals.Health`, `entity.path`
Built-in functions: `distance(A, B)`, `contains(node, kind)`, `count(node, kind)`, `sigmoid(x)`, `depth(node)`
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
