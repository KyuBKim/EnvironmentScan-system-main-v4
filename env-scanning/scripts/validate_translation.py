#!/usr/bin/env python3
"""
Translation Validation Gate (v3.4.0)
Post-translation Python-enforced validation.

Runs both:
1. translation_validator.py (structural + term parity)
2. validate_report.py (report profile compliance)

If EITHER fails, the KO file is renamed to *-ko.REJECTED.md and
the script exits with code 1. This prevents invalid translations
from being treated as final deliverables.

Usage:
    python3 env-scanning/scripts/validate_translation.py \
        --en path/to/report-en.md \
        --ko path/to/report-ko.md \
        --profile standard \
        [--terms env-scanning/config/translation-terms.yaml]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

VERSION = "1.0.0"


def run_translation_validator(en: Path, ko: Path, terms: Path) -> bool:
    """Run translation_validator.py and return True if PASS or WARN."""
    cmd = [
        sys.executable,
        str(Path(__file__).parent.parent / "core" / "translation_validator.py"),
        "--en", str(en),
        "--ko", str(ko),
    ]
    if terms.exists():
        cmd.extend(["--terms", str(terms)])

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Exit code 0 = PASS, 2 = WARN (acceptable), 1 = FAIL
    return result.returncode != 1


def run_report_validator(ko: Path, profile: str) -> bool:
    """Run validate_report.py on KO file and return True if PASS or WARN."""
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "validate_report.py"),
        str(ko),
        "--profile", profile,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode != 1


def main():
    parser = argparse.ArgumentParser(description="Translation Validation Gate")
    parser.add_argument("--en", required=True, help="EN source report path")
    parser.add_argument("--ko", required=True, help="KO translated report path")
    parser.add_argument("--profile", required=True, help="validate_report profile (standard, naver, etc.)")
    parser.add_argument("--terms", default="env-scanning/config/translation-terms.yaml",
                        help="Translation terms YAML path")
    args = parser.parse_args()

    en_path = Path(args.en)
    ko_path = Path(args.ko)
    terms_path = Path(args.terms)

    if not en_path.exists():
        print(f"FATAL: EN file not found: {en_path}", file=sys.stderr)
        sys.exit(1)
    if not ko_path.exists():
        print(f"FATAL: KO file not found: {ko_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Translation Validation Gate v{VERSION}")
    print(f"  EN: {en_path}")
    print(f"  KO: {ko_path}")
    print(f"  Profile: {args.profile}")
    print()

    # 1. Translation structural + term parity
    print("=== Step 1: Translation Validator ===")
    tv_pass = run_translation_validator(en_path, ko_path, terms_path)
    print()

    # 2. Report profile compliance
    print("=== Step 2: Report Profile Validator ===")
    rp_pass = run_report_validator(ko_path, args.profile)
    print()

    # 3. Verdict
    if tv_pass and rp_pass:
        print(f"✅ PASS — {ko_path.name} is a valid KO translation.")
        sys.exit(0)
    else:
        failures = []
        if not tv_pass:
            failures.append("Translation structural/term parity")
        if not rp_pass:
            failures.append("Report profile compliance")

        # Rename to .REJECTED to prevent use as deliverable
        rejected_path = ko_path.with_suffix(".REJECTED.md")
        ko_path.rename(rejected_path)

        print(f"❌ FAIL — {ko_path.name} rejected and renamed to {rejected_path.name}")
        print(f"   Failures: {', '.join(failures)}")
        print(f"   Action: Fix translation and re-run /translate")
        sys.exit(1)


if __name__ == "__main__":
    main()
