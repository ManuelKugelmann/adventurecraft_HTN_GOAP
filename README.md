# AdventureCraft HTN-GOAP Dataset

Universal behavior dataset for agent-based simulation. Three data types, one expression language, one file format.

## Data Types

| Type | What | Evaluation |
|------|------|------------|
| `rule` | trigger → state change | every tick × dt, no agency |
| `role` | prioritized behavior rules | every tick, reactive |
| `plan` | sequential do/wait steps | on goal selection, proactive |

## Quick Start

```bash
# Bootstrap (WSL2 or Linux)
chmod +x bootstrap.sh && ./bootstrap.sh

# Or manually
gh repo create adventurecraft-htn --public --clone
pip install -r requirements.txt

# Extract a batch
python tools/extract.py --source everyday --batch 5

# Validate
python tools/validate.py data/

# Coverage report
python tools/coverage.py
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
        recon: do Sense.Indirect { target = $vault, secrecy = 0.8 }
        grab:  do Transfer.Direct { source = $vault, secrecy = 0.9 }
    }
    done { self.inventory.value > 1000 }
}
```

## Pipeline

```
Cron daily     → extract.yml   → LLM extracts batch → validates → PR
PR merged      → validate.yml  → blocks invalid data
Merge to main  → counters.yml  → generates counter-plans → PR
Weekly Monday  → coverage.yml  → gap report as issue
```

## Structure

```
data/raw/        LLM-extracted, unverified
data/verified/   human-reviewed
tools/           extraction, validation, coverage, counters
prompts/         Claude API system prompts
schema/          expression grammar, entity schema
```

## Contributing

1. Fork and clone
2. Add/edit `.acf` files in `data/raw/` or `data/verified/`
3. Run `python tools/validate.py` on your changes
4. PR — CI validates automatically

## License

MIT
