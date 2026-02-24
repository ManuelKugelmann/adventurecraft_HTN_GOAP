#!/usr/bin/env python3
"""
Extract rules/roles/plans from source material via Claude API.
Outputs .acf files to data/raw/<source>/.

Authoritative spec: https://github.com/ManuelKugelmann/adventurecraft_WIP
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
    # ── Narrative Structure Taxonomies ──────────
    "propp": {
        "desc": "Propp's 31 narrative functions",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "tvtropes": {
        "desc": "TVTropes tropes, plot devices, archetypes, narrative beats",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "folklore": {
        "desc": "ATU folktale index (~2500 tale types)",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "booker": {
        "desc": "Christopher Booker's Seven Basic Plots",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "campbell": {
        "desc": "Joseph Campbell's monomyth / Hero's Journey stages",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "tobias": {
        "desc": "Ronald Tobias' 20 Master Plots",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "polti": {
        "desc": "Georges Polti's 36 Dramatic Situations",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "snyder": {
        "desc": "Blake Snyder's Save the Cat beat sheet categories",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "dramatica": {
        "desc": "Dramatica theory story points",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    # ── Game AI / Design References ─────────────
    "dwarf_fortress": {
        "desc": "Dwarf Fortress emergent behaviors, job trees, need hierarchies",
        "types": ["roles", "plans", "rules"],
        "prompt": "extract_roles.md",
    },
    "rimworld": {
        "desc": "RimWorld AI task trees (ThinkerNodes, JobGivers)",
        "types": ["roles", "plans"],
        "prompt": "extract_roles.md",
    },
    "goap_strips": {
        "desc": "STRIPS/GOAP operator libraries (F.E.A.R., Jeff Orkin)",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "utility_ai": {
        "desc": "Utility AI behavior catalogs (Dave Mark GDC)",
        "types": ["roles"],
        "prompt": "extract_roles.md",
    },
    "paradox": {
        "desc": "CK3/EU4 AI decision trees (diplomacy, war, economy)",
        "types": ["plans", "roles", "rules"],
        "prompt": "extract_plans.md",
    },
    "sims": {
        "desc": "The Sims need/interaction catalogs",
        "types": ["roles", "rules"],
        "prompt": "extract_roles.md",
    },
    "civ": {
        "desc": "Civilization tech/decision trees",
        "types": ["plans", "rules"],
        "prompt": "extract_plans.md",
    },
    "gym_envs": {
        "desc": "OpenAI Gym / PettingZoo environment action spaces",
        "types": ["compounds"],
        "prompt": "extract_compounds.md",
    },
    # ── Behavioral / Social Science ─────────────
    "maslow": {
        "desc": "Maslow's hierarchy (need decomposition)",
        "types": ["rules", "roles"],
        "prompt": "extract_rules.md",
    },
    "bdi": {
        "desc": "BDI (Belief-Desire-Intention) agent literature",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "goffman": {
        "desc": "Erving Goffman's interaction rituals / face-work",
        "types": ["rules", "compounds"],
        "prompt": "extract_rules.md",
    },
    "game_theory": {
        "desc": "Game theory canonical scenarios",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    "org_behavior": {
        "desc": "Organizational behavior (delegation, authority, conflict)",
        "types": ["roles", "plans", "rules"],
        "prompt": "extract_roles.md",
    },
    "strategy": {
        "desc": "Sun Tzu / Clausewitz strategy decompositions",
        "types": ["plans", "compounds"],
        "prompt": "extract_plans.md",
    },
    # ── Domain-Specific Action Catalogs ─────────
    "everyday": {
        "desc": "Everyday life plans (farming, trade, social)",
        "types": ["roles", "plans", "rules"],
        "prompt": "extract_roles.md",
    },
    "military": {
        "desc": "Military doctrine (FM 3-0, FM 3-90)",
        "types": ["plans", "roles", "rules"],
        "prompt": "extract_plans.md",
    },
    "world_rules": {
        "desc": "World mechanics (physics, biology, economics)",
        "types": ["rules"],
        "prompt": "extract_rules.md",
    },
    "medieval_guilds": {
        "desc": "Medieval occupation/guild task lists (historical)",
        "types": ["roles", "plans"],
        "prompt": "extract_roles.md",
    },
    "dnd_srd": {
        "desc": "D&D/Pathfinder SRD (action economy, spell/ability taxonomies)",
        "types": ["plans", "compounds", "roles"],
        "prompt": "extract_plans.md",
    },
    "gurps": {
        "desc": "GURPS action catalogs",
        "types": ["compounds"],
        "prompt": "extract_compounds.md",
    },
    "wikipedia": {
        "desc": "Wikipedia list pages (occupations, crimes, trade goods)",
        "types": ["roles", "rules"],
        "prompt": "extract_roles.md",
    },
    "wikidata": {
        "desc": "Wikidata structured knowledge graphs",
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

BOOKER_PLOTS = [
    "overcoming_the_monster", "rags_to_riches", "the_quest",
    "voyage_and_return", "comedy", "tragedy", "rebirth",
]

CAMPBELL_STAGES = [
    "call_to_adventure", "refusal_of_the_call", "supernatural_aid",
    "crossing_the_threshold", "belly_of_the_whale", "road_of_trials",
    "meeting_with_the_goddess", "temptation", "atonement_with_father",
    "apotheosis", "the_ultimate_boon", "refusal_of_return",
    "magic_flight", "rescue_from_without", "crossing_return_threshold",
    "master_of_two_worlds", "freedom_to_live",
]

TOBIAS_PLOTS = [
    "quest", "adventure", "pursuit", "rescue", "escape", "revenge",
    "the_riddle", "rivalry", "underdog", "temptation", "metamorphosis",
    "transformation", "maturation", "love", "forbidden_love",
    "sacrifice", "discovery", "wretched_excess", "ascension", "descension",
]

POLTI_SITUATIONS = [
    "supplication", "deliverance", "crime_pursued_by_vengeance",
    "vengeance_taken_for_kin", "pursuit", "disaster", "falling_prey_to_cruelty",
    "revolt", "daring_enterprise", "abduction", "the_enigma",
    "obtaining", "enmity_of_kin", "rivalry_of_kin", "murderous_adultery",
    "madness", "fatal_imprudence", "involuntary_crimes_of_love",
    "slaying_of_kin_unrecognized", "self_sacrifice_for_ideal",
    "self_sacrifice_for_kin", "all_sacrificed_for_passion",
    "necessity_of_sacrificing_loved", "rivalry_of_superior_and_inferior",
    "adultery", "crimes_of_love", "discovery_of_dishonor_of_loved",
    "obstacles_to_love", "an_enemy_loved", "ambition",
    "conflict_with_god", "mistaken_jealousy", "erroneous_judgment",
    "remorse", "recovery_of_lost", "loss_of_loved",
]

GAME_THEORY_SCENARIOS = [
    "prisoners_dilemma", "ultimatum_game", "dictator_game",
    "coordination_game", "chicken_game", "stag_hunt",
    "battle_of_sexes", "matching_pennies", "public_goods",
    "tragedy_of_commons", "auction_theory", "signaling_game",
]

STRATEGY_ITEMS = [
    "flanking_maneuver", "feigned_retreat", "siege_warfare",
    "guerrilla_tactics", "scorched_earth", "divide_and_conquer",
    "force_concentration", "attrition", "blitzkrieg",
    "diplomatic_isolation", "economic_warfare", "intelligence_gathering",
]

MASLOW_NEEDS = [
    "physiological_hunger", "physiological_thirst", "physiological_shelter",
    "safety_physical", "safety_economic", "safety_health",
    "belonging_friendship", "belonging_family", "belonging_community",
    "esteem_achievement", "esteem_recognition", "esteem_status",
    "self_actualization_mastery", "self_actualization_creativity",
]

MEDIEVAL_GUILD_ROLES = [
    "blacksmith", "carpenter", "mason", "weaver", "tanner",
    "baker", "brewer", "chandler", "cooper", "fletcher",
    "apothecary", "scribe", "merchant", "innkeeper", "miller",
    "shepherd", "fisherman", "hunter", "miner", "potter",
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
        "booker": BOOKER_PLOTS,
        "campbell": CAMPBELL_STAGES,
        "tobias": TOBIAS_PLOTS,
        "polti": POLTI_SITUATIONS,
        "game_theory": GAME_THEORY_SCENARIOS,
        "strategy": STRATEGY_ITEMS,
        "maslow": MASLOW_NEEDS,
        "medieval_guilds": MEDIEVAL_GUILD_ROLES,
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
    parser.add_argument("--list-sources", action="store_true", help="List all available sources")
    args = parser.parse_args()

    if args.list_sources:
        for name, info in SOURCES.items():
            print(f"  {name:20s} {info['desc']}")
        return 0

    source_info = SOURCES[args.source]
    prompt_name = source_info["prompt"]

    # Get extraction queue
    if args.item:
        queue = [args.item]
    else:
        queue = get_queue(args.source, args.batch)

    if not queue:
        print(f"Nothing to extract for {args.source} -- queue empty or all done.")
        return

    print(f"Extracting {len(queue)} items from {args.source} ({'local claude' if args.local else 'API'}):")
    for item in queue:
        print(f"  - {item}")

    if args.dry_run:
        print("(dry run -- no calls)")
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
