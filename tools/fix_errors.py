#!/usr/bin/env python3
"""
Auto-fix validation errors in extracted .acf files using Claude.

For each .acf file that fails validation, sends the file content and
error details to Claude and writes back the corrected version.
Retries up to --retries times per file (default 5).

Files that cannot be fixed after all retries are moved to a `failed/`
subdirectory inside the target directory (the "failed heap") so they
are committed in the PR for human review rather than silently lost.

Exit code: 0 (all files valid), 1 (one or more moved to failed heap).
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from schema.acf_schema import quick_validate, ValidationResult

FIX_SYSTEM_PROMPT = """\
You are an expert in the AdventureCraft Format (.acf). Fix validation \
errors in .acf files and return the corrected file.

Key rules:
- Every `do` line MUST have a `name:` prefix (e.g. `step: do Move.Direct { ... }`)
- ALL_CAPS labels only when referenced by `fail =`
- Tags are bare identifiers in `[]`, no quotes
- Approaches are Direct, Indirect, Structured only (NOT Careful, Cautious, etc.)
- Plans use `needs { }` and `outcomes { }` — NOT `precond`, `done`, or `estimates`
- `prob` must be bounded 0..1; use a resolution function (sigmoid) or a literal in 0..1
- Authority and reputation are DERIVED from relationships — never stored as attributes
- Counter blocks: ONLY observable state (pos, weight, faction, garrison, equipped, \
action, terrain, formation, visible). NEVER: drives, plans, knowledge, mood, skills
- `rate` and `prob` are mutually exclusive on rules
- Bare tokens everywhere; quotes ONLY for human-readable strings with spaces

Return ONLY the corrected .acf file content. No markdown fences. No explanation.
"""


def _strip_fences(content: str) -> str:
    """Remove markdown code fences if the model wrapped the output."""
    lines = content.split("\n")
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _error_summary(result: ValidationResult) -> list[str]:
    return (
        [f"ERROR [{e.rule}] {e.path}: {e.message}" for e in result.errors]
        + [f"WARN  [{w.rule}] {w.path}: {w.message}" for w in result.warnings]
    )


def fix_one_api(client, file_content: str, errors: list[str], filename: str) -> str | None:
    """Ask Claude API to fix validation errors. Returns corrected content or None."""
    import anthropic

    error_block = "\n".join(f"  - {e}" for e in errors)
    user_msg = (
        f"Fix these validation errors in this .acf file.\n\n"
        f"ERRORS:\n{error_block}\n\n"
        f"FILE ({filename}):\n{file_content}"
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=FIX_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return _strip_fences(response.content[0].text.strip())
    except anthropic.APIError as e:
        print(f"  API error: {e}", file=sys.stderr)
        return None


def fix_one_local(file_content: str, errors: list[str], filename: str) -> str | None:
    """Use local `claude` CLI to fix validation errors. Returns corrected content or None."""
    error_block = "\n".join(f"  - {e}" for e in errors)
    prompt = (
        f"{FIX_SYSTEM_PROMPT}\n\n"
        f"Fix these validation errors in this .acf file.\n\n"
        f"ERRORS:\n{error_block}\n\n"
        f"FILE ({filename}):\n{file_content}"
    )

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  claude CLI error: {result.stderr.strip()}", file=sys.stderr)
            return None
        return _strip_fences(result.stdout.strip())
    except FileNotFoundError:
        print(
            "FATAL: `claude` CLI not found. Install: npm install -g @anthropic-ai/claude-code",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"  Timeout fixing {filename}", file=sys.stderr)
        return None


def fix_file(
    filepath: Path,
    max_retries: int,
    client,
    use_local: bool,
) -> bool:
    """
    Attempt to fix a single file. Returns True if fixed, False if gave up.
    Writes corrected content back to filepath on success.
    """
    result = quick_validate(str(filepath), filepath.read_text())
    if result.ok:
        return True  # already valid

    print(f"\nFixing: {filepath.name}")
    for line in _error_summary(result):
        print(f"  {line}")

    for attempt in range(1, max_retries + 1):
        print(f"  Attempt {attempt}/{max_retries}...")
        current = filepath.read_text()
        errors = _error_summary(result)

        if use_local:
            new_content = fix_one_local(current, errors, filepath.name)
        else:
            new_content = fix_one_api(client, current, errors, filepath.name)

        if new_content is None:
            print(f"  No response on attempt {attempt}")
            continue

        filepath.write_text(new_content)
        result = quick_validate(str(filepath), new_content)

        if result.ok:
            print(f"  Fixed after {attempt} attempt(s): {filepath.name}")
            return True

        print(f"  Still failing ({len(result.errors)} error(s), {len(result.warnings)} warning(s))")

    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-fix .acf validation errors using Claude (with retry)"
    )
    parser.add_argument("directory", help="Directory of .acf files to fix")
    parser.add_argument(
        "--retries",
        type=int,
        default=5,
        help="Max fix attempts per file (default: 5)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local `claude` CLI (subscription auth) instead of ANTHROPIC_API_KEY",
    )
    args = parser.parse_args()

    target_dir = Path(args.directory)
    if not target_dir.is_dir():
        print(f"FATAL: Not a directory: {target_dir}", file=sys.stderr)
        return 1

    client = None
    if not args.local:
        import anthropic
        client = anthropic.Anthropic()

    files = sorted(target_dir.glob("**/*.acf"))
    if not files:
        print(f"No .acf files in {target_dir}")
        return 0

    fixed_count = 0
    failed_count = 0
    failed_dir = target_dir / "failed"

    for filepath in files:
        # Skip files already in the failed heap
        if filepath.parent.name == "failed":
            continue

        result = quick_validate(str(filepath), filepath.read_text())
        if result.ok:
            continue

        success = fix_file(filepath, args.retries, client, args.local)
        if success:
            fixed_count += 1
        else:
            failed_dir.mkdir(exist_ok=True)
            dest = failed_dir / filepath.name
            shutil.move(str(filepath), str(dest))
            print(f"  GAVE UP: moved to failed heap → {dest}")
            failed_count += 1

    print(
        f"\nFix pass complete: "
        f"{fixed_count} fixed, {failed_count} moved to failed/ heap"
    )
    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
