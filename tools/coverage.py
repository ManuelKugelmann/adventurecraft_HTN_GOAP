#!/usr/bin/env python3
"""
Generate coverage report for the HTN dataset.
Reports: action×approach usage, rule layers, compound categories,
role categories, counter gaps, and overall completeness.
"""

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from schema.acf_schema import ACTIONS, APPROACHES, VALID_ACTION_REFS, coverage_categories

DATA_DIR = Path(__file__).parent.parent / "data"


def scan_files(dirpath: Path) -> dict:
    """Scan all .acf files and collect statistics."""
    stats = {
        "total_files": 0,
        "by_type": Counter(),           # rule/role/plan
        "action_usage": Counter(),      # Action.Approach → count
        "tags": Counter(),              # all tags seen
        "has_counter": 0,
        "missing_counter": 0,
        "has_provenance": 0,
        "verified": 0,
        "unverified": 0,
        "rule_layers": Counter(),
        "max_depth": 0,
        "step_count": 0,
        "method_count": 0,
        "files_by_tag": defaultdict(list),
    }

    for filepath in sorted(dirpath.rglob("*.acf")):
        if ".stats" in filepath.stem:
            continue

        content = filepath.read_text()
        stats["total_files"] += 1

        # Detect type from first keyword
        for dtype in ("rule", "role", "plan"):
            if re.match(rf"^{dtype}\s+", content, re.MULTILINE):
                stats["by_type"][dtype] += 1
                break

        # Tags
        tag_match = re.search(r"\[([^\]]+)\]", content)
        if tag_match:
            tags = [t.strip() for t in tag_match.group(1).split(",")]
            for tag in tags:
                stats["tags"][tag] += 1
                stats["files_by_tag"][tag].append(str(filepath))

        # Action usage
        for m in re.finditer(r"do\s+(\w+\.\w+)", content):
            ref = m.group(1)
            if ref in VALID_ACTION_REFS:
                stats["action_usage"][ref] += 1

        # Counter presence
        if "counter " in content:
            stats["has_counter"] += 1
        elif content.strip().startswith("plan "):
            stats["missing_counter"] += 1

        # Provenance
        if "_provenance" in content:
            stats["has_provenance"] += 1
        if "verified = true" in content:
            stats["verified"] += 1
        else:
            stats["unverified"] += 1

        # Rule layers
        for layer in ("L0", "L1", "L2", "L3", "L4"):
            if layer in content:
                stats["rule_layers"][layer] += 1

        # Methods and steps
        stats["method_count"] += len(re.findall(r"^\s+method\s+", content, re.MULTILINE))
        stats["step_count"] += len(re.findall(r"^\s+\w+:\s+do\s+", content, re.MULTILINE))

    return stats


def format_matrix(stats: dict) -> str:
    """Format action×approach coverage matrix."""
    lines = []
    lines.append("Action×Approach Coverage:")
    lines.append(f"{'':15} {'Direct':>8} {'Careful':>8} {'Indirect':>8} {'Total':>8}")
    lines.append("-" * 50)

    for action in ACTIONS:
        counts = []
        for approach in APPROACHES:
            key = f"{action}.{approach}"
            counts.append(stats["action_usage"].get(key, 0))
        total = sum(counts)
        line = f"{action:15} {counts[0]:8} {counts[1]:8} {counts[2]:8} {total:8}"
        lines.append(line)

    return "\n".join(lines)


def format_report(stats: dict) -> str:
    """Format full coverage report."""
    lines = []
    lines.append("=" * 60)
    lines.append("HTN-GOAP Dataset Coverage Report")
    lines.append("=" * 60)
    lines.append("")

    # Overview
    lines.append(f"Total files:     {stats['total_files']}")
    lines.append(f"  Rules:         {stats['by_type'].get('rule', 0)}")
    lines.append(f"  Roles:         {stats['by_type'].get('role', 0)}")
    lines.append(f"  Plans:         {stats['by_type'].get('plan', 0)}")
    lines.append(f"  Methods:       {stats['method_count']}")
    lines.append(f"  Steps:         {stats['step_count']}")
    lines.append(f"  Verified:      {stats['verified']}")
    lines.append(f"  Unverified:    {stats['unverified']}")
    lines.append("")

    # Action matrix
    lines.append(format_matrix(stats))
    lines.append("")

    # Rule layers
    lines.append("Rule Layers:")
    for layer in ("L0", "L1", "L2", "L3", "L4"):
        count = stats["rule_layers"].get(layer, 0)
        lines.append(f"  {layer}: {count} rules")
    lines.append("")

    # Counter gaps
    lines.append("Counters:")
    lines.append(f"  Plans with counters:    {stats['has_counter']}")
    lines.append(f"  Plans without counters: {stats['missing_counter']}")
    if stats["has_counter"] + stats["missing_counter"] > 0:
        pct = stats["has_counter"] / (stats["has_counter"] + stats["missing_counter"]) * 100
        lines.append(f"  Coverage:               {pct:.0f}%")
    lines.append("")

    # Top tags
    lines.append("Top tags:")
    for tag, count in stats["tags"].most_common(20):
        lines.append(f"  {tag:25} {count}")
    lines.append("")

    # Gaps
    lines.append("Gaps (zero-usage action×approach):")
    gaps = []
    for action in ACTIONS:
        for approach in APPROACHES:
            key = f"{action}.{approach}"
            if stats["action_usage"].get(key, 0) == 0:
                gaps.append(key)
    if gaps:
        for g in gaps:
            lines.append(f"  ⚠ {g}")
    else:
        lines.append("  None — all combinations used")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="HTN dataset coverage report")
    parser.add_argument("--dir", default=str(DATA_DIR), help="Data directory")
    parser.add_argument("--markdown", action="store_true", help="Output as markdown")
    args = parser.parse_args()

    stats = scan_files(Path(args.dir))

    if stats["total_files"] == 0:
        print("No .acf files found.", file=sys.stderr)
        return 1

    report = format_report(stats)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
