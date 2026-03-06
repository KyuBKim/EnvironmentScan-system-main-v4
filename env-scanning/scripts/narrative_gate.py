#!/usr/bin/env python3
"""Narrative Gate — Phase B4 Python verification for Timeline Map narratives.

Validates that LLM-generated narratives meet structural and data-integrity
requirements before proceeding to skeleton assembly (Phase C).
This enforces the Python 원천봉쇄 principle at the narrative boundary.

Usage:
    python3 narrative_gate.py \
        --narratives <narratives.json> \
        --data-package <data-package.json> \
        [--challenges <challenges.json>] \
        [--output <gate-results.json>]

Exit codes:
    0 = PASS (all checks passed)
    1 = FAIL (one or more CRITICAL checks failed)
    2 = WARN (warnings only)
"""

VERSION = "1.0.0"

import argparse
import json
import re
import sys


class GateResult:
    def __init__(self):
        self.checks = []

    def add(self, check_id: str, severity: str, description: str,
            passed: bool, detail: str = ""):
        self.checks.append({
            "check_id": check_id,
            "severity": severity,
            "description": description,
            "passed": passed,
            "detail": detail,
        })

    @property
    def has_critical(self) -> bool:
        return any(not c["passed"] and c["severity"] == "CRITICAL"
                   for c in self.checks)

    @property
    def has_warn(self) -> bool:
        return any(not c["passed"] and c["severity"] == "WARN"
                   for c in self.checks)

    def summary(self) -> str:
        lines = []
        for c in self.checks:
            status = "PASS" if c["passed"] else c["severity"]
            line = f"  [{status}] {c['check_id']}: {c['description']}"
            if c["detail"]:
                line += f" — {c['detail']}"
            lines.append(line)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "validator": "narrative_gate.py",
            "version": VERSION,
            "total_checks": len(self.checks),
            "passed": sum(1 for c in self.checks if c["passed"]),
            "failed": sum(1 for c in self.checks if not c["passed"]),
            "checks": self.checks,
        }


def validate_narratives(
    narratives: dict, data_package: dict, challenges: dict | None = None
) -> GateResult:
    """Run all narrative gate checks."""
    gate = GateResult()
    theme_narratives = narratives.get("theme_narratives", [])
    pre_rendered = data_package.get("pre_rendered", {})
    theme_analysis = data_package.get("theme_analysis", {})

    # ── NG-001: Required fields present ──
    # Each theme narrative must have trajectory, judgment, next_expected.
    missing_fields = []
    required_fields = ["trajectory", "judgment", "next_expected"]
    for tn in theme_narratives:
        tid = tn.get("theme_id", "unknown")
        for field in required_fields:
            if not tn.get(field) or not str(tn[field]).strip():
                missing_fields.append(f"{tid}.{field}")
    gate.add(
        "NG-001", "CRITICAL",
        "All themes have trajectory, judgment, next_expected",
        len(missing_fields) == 0,
        f"Missing: {missing_fields}" if missing_fields else ""
    )

    # ── NG-002: Numeric values in narratives exist in data-package ──
    # Extract all numbers from narrative text and verify they appear in data-package.
    # Collect known numeric values from data-package.
    known_numbers = set()

    # From theme_analysis stats
    for key, val in theme_analysis.items():
        if isinstance(val, dict):
            stats = val.get("stats", {})
            for sv in stats.values():
                if isinstance(sv, (int, float)):
                    known_numbers.add(str(sv))
                    if isinstance(sv, float):
                        known_numbers.add(f"{sv:.1f}")
                        known_numbers.add(f"{sv:.2f}")
            signal_count = val.get("signal_count", val.get("total_signals"))
            if signal_count is not None:
                known_numbers.add(str(signal_count))

    # From pre_rendered
    for section_key, section_val in pre_rendered.items():
        _extract_numbers_recursive(section_val, known_numbers)

    # From psst_rankings
    for entry in data_package.get("psst_rankings", []):
        for v in entry.values():
            if isinstance(v, (int, float)):
                known_numbers.add(str(v))
                if isinstance(v, float):
                    known_numbers.add(f"{v:.1f}")
                    known_numbers.add(f"{v:.2f}")

    # Common numbers that are not meaningful to check
    trivial_numbers = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
                       "100", "1000", "2026", "2025", "2024", "2023"}

    # Extract numbers from narrative text
    suspicious_numbers = []
    for tn in theme_narratives:
        tid = tn.get("theme_id", "unknown")
        for field in ["trajectory", "judgment", "next_expected"]:
            text = str(tn.get(field, ""))
            # Find numbers that look like metrics (not dates, not trivial)
            nums = re.findall(r"(?<!\d[-/])\b(\d+\.?\d*)\b(?![-/]\d)", text)
            for n in nums:
                if n not in trivial_numbers and n not in known_numbers:
                    # Check if it's part of a date pattern
                    if not re.search(rf"\d{{4}}-\d{{2}}-{re.escape(n)}", text):
                        suspicious_numbers.append(f"{tid}: {n}")

    gate.add(
        "NG-002", "WARN",
        "Numeric values in narratives exist in data-package",
        len(suspicious_numbers) == 0,
        f"Suspicious: {suspicious_numbers[:5]}" if suspicious_numbers else ""
    )

    # ── NG-003: Each trajectory has ≥2 date references ──
    date_pattern = r"\b\d{4}-\d{2}-\d{2}\b"
    low_date_themes = []
    for tn in theme_narratives:
        tid = tn.get("theme_id", "unknown")
        trajectory = str(tn.get("trajectory", ""))
        dates = re.findall(date_pattern, trajectory)
        if len(dates) < 2:
            low_date_themes.append(f"{tid} (found {len(dates)})")
    gate.add(
        "NG-003", "CRITICAL",
        "Each trajectory has ≥2 date references",
        len(low_date_themes) == 0,
        f"Insufficient dates: {low_date_themes}" if low_date_themes else ""
    )

    # ── NG-004: Cross-theme synthesis has ≥2 interactions + ≥3 implications ──
    synthesis = narratives.get("cross_theme_synthesis", {})
    interactions = synthesis.get("interactions", [])
    implications = synthesis.get("strategic_implications", [])
    ng004_issues = []
    if len(interactions) < 2:
        ng004_issues.append(f"interactions={len(interactions)} (need ≥2)")
    if len(implications) < 3:
        ng004_issues.append(f"implications={len(implications)} (need ≥3)")
    gate.add(
        "NG-004", "CRITICAL",
        "Cross-theme synthesis: ≥2 interactions + ≥3 implications",
        len(ng004_issues) == 0,
        "; ".join(ng004_issues) if ng004_issues else ""
    )

    # ── NG-005: Refinement completeness (conditional) ──
    # Only checked when challenges input is provided (B3 refinement mode).
    if challenges is not None:
        challenge_list = challenges.get("challenges", [])
        must_address = [c for c in challenge_list
                        if c.get("severity") == "must_address"]
        refinement_log = narratives.get("refinement_log", [])

        # Build set of addressed challenge indices
        addressed_indices = set()
        for entry in refinement_log:
            if entry.get("action") == "addressed":
                addressed_indices.add(entry.get("challenge_index"))

        unaddressed = []
        for i, ch in enumerate(must_address):
            # Find original index in the full challenge list
            orig_idx = challenge_list.index(ch)
            if orig_idx not in addressed_indices:
                unaddressed.append(f"challenge[{orig_idx}]: {ch.get('finding', '')[:60]}")

        gate.add(
            "NG-005", "CRITICAL",
            "All must_address challenges addressed in refinement",
            len(unaddressed) == 0,
            f"Unaddressed: {unaddressed}" if unaddressed else ""
        )
    else:
        gate.add(
            "NG-005", "CRITICAL",
            "All must_address challenges addressed in refinement",
            True,
            "Skipped — no challenges input (draft mode)"
        )

    return gate


def _extract_numbers_recursive(obj, numbers_set: set):
    """Recursively extract numeric values from nested data structures."""
    if isinstance(obj, (int, float)):
        numbers_set.add(str(obj))
        if isinstance(obj, float):
            numbers_set.add(f"{obj:.1f}")
            numbers_set.add(f"{obj:.2f}")
    elif isinstance(obj, dict):
        for v in obj.values():
            _extract_numbers_recursive(v, numbers_set)
    elif isinstance(obj, list):
        for item in obj:
            _extract_numbers_recursive(item, numbers_set)
    elif isinstance(obj, str):
        # Extract inline numbers from pre-rendered strings (e.g., ASCII art)
        nums = re.findall(r"\b(\d+\.?\d*)\b", obj)
        for n in nums:
            numbers_set.add(n)


def main():
    parser = argparse.ArgumentParser(
        description="Narrative Gate — Phase B4 Python verification"
    )
    parser.add_argument("--narratives", required=True,
                        help="Path to narratives JSON (draft or refined)")
    parser.add_argument("--data-package", required=True,
                        help="Path to data-package JSON")
    parser.add_argument("--challenges", default=None,
                        help="Path to challenges JSON (enables NG-005 refinement check)")
    parser.add_argument("--output", default=None,
                        help="Optional path to write gate results JSON")
    args = parser.parse_args()

    try:
        with open(args.narratives, "r", encoding="utf-8") as f:
            narratives = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Narratives not found: {args.narratives}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid narratives JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.data_package, "r", encoding="utf-8") as f:
            data_package = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Data-package not found: {args.data_package}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid data-package JSON: {e}", file=sys.stderr)
        sys.exit(1)

    challenges = None
    if args.challenges:
        try:
            with open(args.challenges, "r", encoding="utf-8") as f:
                challenges = json.load(f)
        except FileNotFoundError:
            print(f"ERROR: Challenges not found: {args.challenges}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid challenges JSON: {e}", file=sys.stderr)
            sys.exit(1)

    gate = validate_narratives(narratives, data_package, challenges)

    print("Narrative Gate — Phase B4 Verification")
    print(f"{'=' * 60}")
    print(gate.summary())
    print(f"{'=' * 60}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(gate.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"Gate results written to {args.output}")

    if gate.has_critical:
        print("RESULT: FAIL — narrative quality gate failed")
        sys.exit(1)
    elif gate.has_warn:
        print("RESULT: WARN — advisory issues found")
        sys.exit(2)
    else:
        print("RESULT: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
