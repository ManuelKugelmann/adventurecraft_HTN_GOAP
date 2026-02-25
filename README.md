# AdventureCraft HTN-GOAP Dataset

Universal behavior dataset for agent-based simulation. Three data types, one expression language, one file format.

Authoritative game spec: https://github.com/ManuelKugelmann/adventurecraft_WIP

## Data Types

| Type | What | Evaluation |
|------|------|------------|
| `rule` | trigger -> state change | every tick x dt, no agency |
| `role` | prioritized behavior rules | every tick, reactive |
| `plan` | sequential do/wait steps | on goal selection, proactive |

## Quick Start

```bash
pip install -r requirements.txt

# Extract a batch (API key)
python tools/extract.py --source everyday --batch 5

# Extract (local claude CLI, subscription auth)
python tools/extract.py --source propp --batch 5 --local

# List all 30+ extraction sources
python tools/extract.py --source propp --list-sources

# Validate
python tools/validate.py data/

# Coverage report
python tools/coverage.py

# Run tests
pytest tools/tests/ -v
```

## File Format: `.acf`

```acf
rule fire_spread [physics, L0] {
    spread: when region.fire > 0 AND adjacent.has(Flammable),
            prob = region.fire * 0.1 * region.wind,
            effect: adjacent.fire += 20
}

role farmer [economic, rural] {
    plow:    when season == spring AND field.state == fallow,
             do Modify.Direct { target = $field }, priority = 10
}

plan criminal.heist [criminal, economic] {
    method classic {
        recon: do Sense.Structured { target = $vault, secrecy = 0.8 }
        grab:  do Transfer.Direct { source = $vault, secrecy = 0.9 }
    }
    done { self.inventory.value > 1000 }
}
```

## Actions (7 x 3)

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

## Extraction Sources

30+ sources across four categories:

- **Narrative**: Propp, ATU folklore, TVTropes, Campbell, Booker, Tobias, Polti, Snyder, Dramatica
- **Game AI**: Dwarf Fortress, RimWorld, STRIPS/GOAP, Utility AI, CK3/EU4, The Sims, Civilization
- **Behavioral Science**: Maslow, BDI agents, Goffman, game theory, org behavior, Sun Tzu/Clausewitz
- **Domain Catalogs**: Medieval guilds, military doctrine, D&D/Pathfinder SRD, GURPS, Wikipedia, Wikidata

Full catalog: [docs/sources.md](docs/sources.md)

## CI/CD Pipeline

```
Push/PR         -> test.yml      -> pytest + validate all seed data
PR (data/)      -> validate.yml  -> blocks invalid .acf files
Cron daily      -> extract.yml   -> LLM extracts batch -> validates -> PR
Merge to main   -> counters.yml  -> generates counter-plans -> PR
Weekly Monday   -> coverage.yml  -> gap report as issue
```

## Structure

```
data/
  raw/             LLM-extracted, unverified
  verified/        human-reviewed, ships with game
prompts/           extraction prompts per data type
tools/             extraction, validation, coverage, counters
  tests/           pytest suite
schema/            expression grammar, entity schema
docs/              source catalog, specs
.github/workflows/ CI/CD automation
```

## Contributing

1. Fork and clone
2. Add/edit `.acf` files in `data/raw/` or `data/verified/`
3. Run `python tools/validate.py` on your changes
4. Run `pytest tools/tests/` to verify
5. PR -- CI validates automatically

## License

MIT
