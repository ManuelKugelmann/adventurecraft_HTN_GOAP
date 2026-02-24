#!/usr/bin/env python3
"""
Extract rules/roles/plans from source material via Claude API.
Outputs .acf files to data/raw/<source>/.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

SOURCES = {
    "propp": {
        "desc": "Propp's 31 narrative functions",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "military": {
        "desc": "Military doctrine (FM 3-0, FM 3-90)",
        "types": ["plans", "roles", "rules"],
        "prompt": "extract_plans.md",
    },
    "everyday": {
        "desc": "Everyday life plans (farming, trade, social)",
        "types": ["roles", "plans", "rules"],
        "prompt": "extract_roles.md",
    },
    "tvtropes": {
        "desc": "TVTropes narrative patterns",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "folklore": {
        "desc": "ATU folktale index",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "world_rules": {
        "desc": "World mechanics (physics, biology, economics)",
        "types": ["rules"],
        "prompt": "extract_rules.md",
    },
}

# ── Extraction queues per source ──────────────

PROPP_FUNCTIONS = [
    "absentation", "interdiction", "violation", "reconnaissance",
    "delivery", "trickery", "complicity", "villainy", "lack",
    "mediation", "counteraction", "departure", "donor_testing",
    "hero_reaction", "magical_agent", "guidance", "struggle",
    "branding", "victory", "liquidation", "return", "pursuit",
    "rescue", "unrecognized_arrival", "unfounded_claims",
    "difficult_task", "solution", "recognition", "exposure",
    "transfiguration", "punishment", "wedding",
]

EVERYDAY_CATEGORIES = [
    "farming_seasonal_cycle", "livestock_herding", "fishing",
    "cooking_meals", "food_preservation", "water_collection",
    "building_shelter", "tool_maintenance", "textile_production",
    "market_trading", "barter_negotiation", "debt_collection",
    "greeting_stranger", "hosting_guest", "courtship",
    "marriage_ceremony", "funeral_rites", "naming_ceremony",
    "dispute_resolution", "community_gathering", "teaching_child",
    "apprenticeship", "healing_sick", "midwifery",
    "guard_patrol", "militia_drill", "messenger_run",
    "tax_collection", "census_taking", "law_enforcement",
    "prayer_ritual", "pilgrimage", "harvest_festival",
]

WORLD_RULE_CATEGORIES = [
    "temperature", "water_cycle", "fire", "light",
    "crop_growth", "metabolism", "disease", "aging", "healing",
    "item_decay", "structure_decay", "fuel_consumption",
    "social_judgment", "familiarity", "knowledge_propagation", "mood",
    "supply_demand", "supply_depletion",
]


def load_prompt(prompt_name: str) -> str:
    path = PROMPTS_DIR / prompt_name
    if not path.exists():
        print(f"FATAL: Prompt file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text()


def get_queue(source: str, batch_size: int) -> list[str]:
    """Get next batch of items to extract from source queue."""
    queues = {
        "propp": PROPP_FUNCTIONS,
        "everyday": EVERYDAY_CATEGORIES,
        "world_rules": WORLD_RULE_CATEGORIES,
    }
    queue = queues.get(source, [f"{source}_batch_{i}" for i in range(batch_size)])

    # Filter already extracted
    out_dir = RAW_DIR / source
    existing = {p.stem for p in out_dir.glob("*.acf")} if out_dir.exists() else set()
    remaining = [item for item in queue if item not in existing]

    return remaining[:batch_size]


def extract_one_api(client, system_prompt: str, item: str, source: str) -> str | None:
    """Call Claude API to extract one item. Returns .acf content or None."""
    import anthropic

    user_msg = f"""Extract game data for: {item}
Source domain: {source}
Output format: .acf (AdventureCraft Format)

Return ONLY the .acf file content. No markdown fences. No explanation."""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            content = response.content[0].text.strip()
            return _strip_fences(content)

        except anthropic.APIError as e:
            print(f"  API error (attempt {attempt+1}/3): {e}", file=sys.stderr)
            if attempt == 2:
                return None

    return None


def extract_one_local(system_prompt: str, item: str, source: str) -> str | None:
    """Call local `claude` CLI (uses subscription auth). Returns .acf content or None."""
    user_msg = f"""Extract game data for: {item}
Source domain: {source}
Output format: .acf (AdventureCraft Format)

Return ONLY the .acf file content. No markdown fences. No explanation."""

    full_prompt = f"{system_prompt}\n\n---\n\n{user_msg}"

    try:
        result = subprocess.run(
            ["claude", "-p", full_prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"  claude CLI error: {result.stderr.strip()}", file=sys.stderr)
            return None

        content = result.stdout.strip()
        return _strip_fences(content)

    except FileNotFoundError:
        print("FATAL: `claude` CLI not found. Install: npm install -g @anthropic-ai/claude-code", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"  Timeout extracting {item}", file=sys.stderr)
        return None


def _strip_fences(content: str) -> str:
    """Remove markdown code fences if present."""
    if content.startswith("```"):
        content = "\n".join(content.split("\n")[1:])
    if content.endswith("```"):
        content = "\n".join(content.split("\n")[:-1])
    return content


def add_provenance(content: str, item: str, source: str, prompt_version: str) -> str:
    """Append _provenance block if not already present."""
    if "_provenance" in content:
        return content

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    provenance = f"""
_provenance {{
    sources = [{{ type = {source}, id = {item}, confidence = 0.7 }}]
    model = claude-sonnet-4-20250514
    prompt_version = {prompt_version}
    timestamp = {now}
    verified = false
}}
"""
    return content.rstrip() + "\n" + provenance


def main():
    parser = argparse.ArgumentParser(description="Extract HTN data from sources via Claude API")
    parser.add_argument("--source", required=True, choices=list(SOURCES.keys()))
    parser.add_argument("--batch", type=int, default=5, help="Batch size")
    parser.add_argument("--item", type=str, help="Extract specific item (skip queue)")
    parser.add_argument("--local", action="store_true", help="Use local `claude` CLI (subscription auth)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be extracted")
    args = parser.parse_args()

    source_info = SOURCES[args.source]
    prompt_name = source_info["prompt"]

    # Get extraction queue
    if args.item:
        queue = [args.item]
    else:
        queue = get_queue(args.source, args.batch)

    if not queue:
        print(f"Nothing to extract for {args.source} — queue empty or all done.")
        return

    print(f"Extracting {len(queue)} items from {args.source} ({'local claude' if args.local else 'API'}):")
    for item in queue:
        print(f"  - {item}")

    if args.dry_run:
        print("(dry run — no calls)")
        return

    # Load prompt
    system_prompt = load_prompt(prompt_name)

    # Init client (API mode only)
    client = None
    if not args.local:
        import anthropic
        client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var

    # Ensure output dir
    out_dir = RAW_DIR / args.source
    out_dir.mkdir(parents=True, exist_ok=True)

    # Extract each item
    successes = 0
    for item in queue:
        print(f"\nExtracting: {item}...")

        if args.local:
            content = extract_one_local(system_prompt, item, args.source)
        else:
            content = extract_one_api(client, system_prompt, item, args.source)

        if content is None:
            print(f"  FAILED: {item}")
            continue

        content = add_provenance(content, item, args.source, prompt_name)

        out_path = out_dir / f"{item}.acf"
        out_path.write_text(content)
        print(f"  OK: {out_path}")
        successes += 1

    print(f"\nDone: {successes}/{len(queue)} succeeded")
    return 0 if successes == len(queue) else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
