#!/usr/bin/env python3
"""
Run all canonical test cases and generate a summary report.

This script runs each canonical test module and collects scores,
providing an overview of baseline performance before Phase 2.2 manual scoring.

Usage:
    python tests/canonicals/run_all_canonicals.py
    python tests/canonicals/run_all_canonicals.py --json  # Output JSON
    python tests/canonicals/run_all_canonicals.py --verbose  # Detailed output
"""

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def import_test_module(module_name: str):
    """Import a test module dynamically."""
    try:
        # Try direct import for pytest context
        module = importlib.import_module(f"tests.canonicals.{module_name}")
        return module
    except ImportError:
        try:
            # Fallback: direct import from current directory
            module_path = Path(__file__).parent / f"{module_name}.py"
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception as e:
            print(f"Warning: Could not import {module_name}: {e}", file=sys.stderr)
            return None


def run_test_function(func):
    """Run a single test function and return score."""
    try:
        result = func()
        if isinstance(result, (int, float)):
            return float(result)
        else:
            return None
    except Exception as e:
        print(f"Error running {func.__name__}: {e}", file=sys.stderr)
        return None


def main():
    verbose = "--verbose" in sys.argv
    output_json = "--json" in sys.argv

    test_modules = [
        "test_factual_no_tool",
        "test_tool_routing_web_search",
        "test_tool_routing_file_op",
        "test_memory_recall_recent",
        "test_memory_recall_semantic",
        "test_memory_miss_novel",
        "test_multistep_parse_tool_store",
        "test_ambiguous_intent",
        "test_injection_prevention",
        "test_context_pruning",
        "test_interrupt_responsiveness",
    ]

    results = {}
    all_scores = []

    for module_name in test_modules:
        module = import_test_module(module_name)
        if not module:
            continue

        category_results = {}

        # Find all test functions in module
        test_functions = [
            (name, getattr(module, name))
            for name in dir(module)
            if name.startswith("test_") and callable(getattr(module, name))
        ]

        for test_name, test_func in test_functions:
            score = run_test_function(test_func)
            if score is not None:
                category_results[test_name] = score
                all_scores.append(score)

                if verbose:
                    print(f"  {test_name}: {score:.3f}")

        if category_results:
            results[module_name] = category_results
            avg = sum(category_results.values()) / len(category_results)
            print(f"{module_name}: {avg:.3f} (n={len(category_results)})")

    # Aggregate statistics
    if all_scores:
        overall_avg = sum(all_scores) / len(all_scores)
        min_score = min(all_scores)
        max_score = max(all_scores)

        print("\n" + "=" * 60)
        print("OVERALL SUMMARY")
        print("=" * 60)
        print(f"Total test functions: {len(all_scores)}")
        print(f"Overall average: {overall_avg:.3f}")
        print(f"Min score: {min_score:.3f}")
        print(f"Max score: {max_score:.3f}")

        # Check against thresholds
        below_0_7 = [s for s in all_scores if s < 0.7]
        if below_0_7:
            print(f"\nWarning: {len(below_0_7)} scores below 0.7 threshold")
            print(f"  Scores: {[f'{s:.3f}' for s in below_0_7]}")

        print("\n" + "=" * 60)
        print("NEXT STEPS: Phase 2.2")
        print("=" * 60)
        print("1. Review any scores below 0.7")
        print("2. Run canonicals with actual agent (not mocks)")
        print("3. Record final baseline scores in evals/baseline_scores.json")
        print("4. Commit baseline_scores.json (immutable reference)")

    if output_json:
        print("\n" + json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
