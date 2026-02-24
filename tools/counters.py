#!/usr/bin/env python3
"""
Generate counter-plans for entries missing them.
Calls Claude API to create observable threat signatures and responses.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
DATA_DIR = Path(__file__).parent.parent / "data"

COUNTER_SYSTEM = """You generate counter-plans for AdventureCraft HTN data.

Given a plan, output a counter block that:
1. Defines a threat signature using ONLY observable state:
   pos, weight, faction, garrison, walls, equipped, visible actions, buildings, terrain
   NEVER reference: drives, plans, knowledge, mood, skills, contracts
2. Lists 2-4 response plans with `when` conditions
3. All conditions use the expression language (entity.path, edge(), sigmoid(), etc.)

Output ONLY the counter block in .acf format. No explanation."""


def find_plans_without_counters(dirpath: Path) -> list[tuple[Path, str]]:
    """Find plan files that have no counter block."""
    gaps = []
    for filepath in sorted(dirpath.rglob("*.acf")):
        if ".stats" in filepath.stem:
            continue
        content = filepath.read_text()
        if re.match(r"^plan\s+", content, re.MULTILINE) and "counter " not in content:
            gaps.append((filepath, content))
    return gaps


def generate_counter(client, filepath: Path, content: str, local: bool = False) -> str | None:
    """Generate counter block for a plan."""
    user_msg = f"""Generate counter-plan block for this plan:

{content}

Output ONLY the counter block to append (starting with `counter threat.xxx {{`).
Use observable state only. 2-4 responses."""

    if local:
        full_prompt = f"{COUNTER_SYSTEM}\n\n---\n\n{user_msg}"
        try:
            result = subprocess.run(
                ["claude", "-p", full_prompt, "--output-format", "text"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                print(f"  claude CLI error: {result.stderr.strip()}", file=sys.stderr)
                return None
            text = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"  Error: {e}", file=sys.stderr)
            return None
    else:
        import anthropic
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=COUNTER_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = response.content[0].text.strip()
        except anthropic.APIError as e:
            print(f"  API error: {e}", file=sys.stderr)
            return None

    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    return text


def main():
    parser = argparse.ArgumentParser(description="Generate counter-plans for gaps")
    parser.add_argument("dir", nargs="?", default=str(DATA_DIR / "verified"))
    parser.add_argument("--batch", type=int, default=10)
    parser.add_argument("--local", action="store_true", help="Use local `claude` CLI")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    gaps = find_plans_without_counters(Path(args.dir))

    if not gaps:
        print("All plans have counters.")
        return 0

    batch = gaps[:args.batch]
    print(f"Found {len(gaps)} plans without counters. Processing {len(batch)}:")
    for filepath, _ in batch:
        print(f"  - {filepath}")

    if args.dry_run:
        return 0

    client = None
    if not args.local:
        import anthropic
        client = anthropic.Anthropic()
    patched = 0

    for filepath, content in batch:
        print(f"\nGenerating counter for {filepath.name}...")
        counter_block = generate_counter(client, filepath, content, local=args.local)

        if counter_block is None:
            print(f"  FAILED")
            continue

        # Append counter block before closing brace
        lines = content.rstrip().rsplit("}", 1)
        if len(lines) == 2:
            new_content = lines[0] + "\n    " + counter_block.replace("\n", "\n    ") + "\n}\n"
            filepath.write_text(new_content)
            print(f"  OK: appended counter block")
            patched += 1
        else:
            print(f"  SKIP: couldn't find insertion point")

    print(f"\nDone: {patched}/{len(batch)} patched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
