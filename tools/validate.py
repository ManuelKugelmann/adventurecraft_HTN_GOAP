#!/usr/bin/env python3
"""
Validate .acf files against the AdventureCraft schema.
Exit code 0 = all valid, 1 = errors found.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from schema.acf_schema import quick_validate, ValidationResult


def validate_file(filepath: Path) -> ValidationResult:
    """Validate a single .acf file."""
    content = filepath.read_text()
    return quick_validate(str(filepath), content)


def validate_dir(dirpath: Path, recursive: bool = True) -> dict[str, ValidationResult]:
    """Validate all .acf files in a directory."""
    results = {}
    pattern = "**/*.acf" if recursive else "*.acf"
    for filepath in sorted(dirpath.glob(pattern)):
        # Skip stats sidecars
        if filepath.suffix == ".acf" and ".stats" in filepath.stem:
            continue
        results[str(filepath)] = validate_file(filepath)
    return results


def main():
    parser = argparse.ArgumentParser(description="Validate .acf files")
    parser.add_argument("paths", nargs="+", help="Files or directories to validate")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--quiet", action="store_true", help="Only show errors")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    all_results: dict[str, ValidationResult] = {}

    for path_str in args.paths:
        path = Path(path_str)
        if path.is_file():
            all_results[str(path)] = validate_file(path)
        elif path.is_dir():
            all_results.update(validate_dir(path))
        else:
            print(f"WARN: {path} not found, skipping", file=sys.stderr)

    if not all_results:
        print("No .acf files found.", file=sys.stderr)
        return 1

    # Report
    total_errors = 0
    total_warnings = 0
    total_files = len(all_results)
    ok_files = 0

    for filepath, result in all_results.items():
        total_errors += len(result.errors)
        total_warnings += len(result.warnings)

        if result.ok and (not args.strict or not result.warnings):
            ok_files += 1
            if not args.quiet:
                print(f"OK    {filepath}")
        else:
            print(f"FAIL  {filepath}")
            print(f"  {result}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Files: {total_files} total, {ok_files} ok, {total_files - ok_files} failed")
    print(f"Errors: {total_errors}, Warnings: {total_warnings}")

    if args.strict:
        return 0 if total_errors == 0 and total_warnings == 0 else 1
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
