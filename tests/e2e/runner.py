"""
Project SAM: Comprehensive Opaque-Box E2E Test Suite Runner.

Executes test tiers, tracks pass/fail metrics, reports feature coverage,
and guarantees exit code 0 on full suite pass.

Usage:
    python tests/e2e/runner.py [--tier 1|2|3|4|all] [-v|--verbose]
"""

from __future__ import annotations

import os
import sys
import time
import inspect
import importlib.util
import argparse
from typing import Callable, Dict, List, Tuple


# Ensure workspace root and test root are in PYTHONPATH
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)


class TestResult:
    def __init__(self, name: str, tier: str, module: str, passed: bool, duration: float, error: str = ""):
        self.name = name
        self.tier = tier
        self.module = module
        self.passed = passed
        self.duration = duration
        self.error = error


class SAMTestRunner:
    def __init__(self, verbose: bool = False, tier_filter: str = "all"):
        self.verbose = verbose
        self.tier_filter = str(tier_filter).lower()
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.results: List[TestResult] = []

    def _discover_modules(self, tier_folder: str) -> List[str]:
        folder_path = os.path.join(self.base_dir, tier_folder)
        if not os.path.exists(folder_path):
            return []
        modules = []
        for f in os.listdir(folder_path):
            if f.startswith("test_") and f.endswith(".py"):
                modules.append(os.path.join(folder_path, f))
        return sorted(modules)

    def _load_and_run_module(self, file_path: str, tier_name: str) -> List[TestResult]:
        mod_name = os.path.splitext(os.path.basename(file_path))[0]
        results = []

        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        if spec is None or spec.loader is None:
            print(f"[ERROR] Could not load module spec for: {file_path}")
            return results

        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            print(f"[FAIL] Module execution failed: {mod_name} -> {e}")
            results.append(TestResult(
                name=f"{mod_name}_load",
                tier=tier_name,
                module=mod_name,
                passed=False,
                duration=0.0,
                error=str(e)
            ))
            return results

        # Find all test_* functions
        for attr_name in dir(module):
            if attr_name.startswith("test_"):
                func = getattr(module, attr_name)
                if callable(func):
                    t0 = time.time()
                    passed = False
                    err_msg = ""
                    try:
                        # Inspect function arguments to handle fixtures if any
                        sig = inspect.signature(func)
                        if len(sig.parameters) == 0:
                            func()
                        else:
                            # Instantiate mock arguments if needed
                            args = []
                            for p in sig.parameters.values():
                                if p.name == "workspace":
                                    from tests.e2e.fixtures import TempWorkspace
                                    args.append(TempWorkspace())
                                elif p.name == "sam_system":
                                    from tests.e2e.harness import SAMSystemFacade
                                    args.append(SAMSystemFacade())
                                elif p.name == "brain":
                                    from tests.e2e.harness import BrainEngineAdapter
                                    args.append(BrainEngineAdapter())
                                elif p.name == "memory":
                                    from tests.e2e.harness import MemoryEngineAdapter
                                    args.append(MemoryEngineAdapter())
                                elif p.name == "controller":
                                    from tests.e2e.harness import ComputerControllerAdapter
                                    args.append(ComputerControllerAdapter())
                                else:
                                    args.append(None)
                            func(*args)
                        passed = True
                    except Exception as ex:
                        import traceback
                        passed = False
                        err_msg = traceback.format_exc()

                    duration = time.time() - t0
                    res = TestResult(
                        name=attr_name,
                        tier=tier_name,
                        module=mod_name,
                        passed=passed,
                        duration=duration,
                        error=err_msg
                    )
                    results.append(res)
                    if self.verbose:
                        status = "PASS" if passed else "FAIL"
                        print(f"  [{status}] {tier_name} :: {mod_name} :: {attr_name} ({duration:.4f}s)")
                        if not passed:
                            print(f"       Error: {err_msg}")
        return results

    def run(self) -> int:
        print("================================================================================")
        print("              PROJECT SAM: OPAQUE-BOX E2E TEST RUNNER                           ")
        print("================================================================================")
        t_start = time.time()

        tiers_to_run = []
        if self.tier_filter in ["1", "all"]:
            tiers_to_run.append(("Tier 1: Feature Coverage", "tier1_features"))
        if self.tier_filter in ["2", "all"]:
            tiers_to_run.append(("Tier 2: Boundary & Corner Cases", "tier2_boundaries"))
        if self.tier_filter in ["3", "all"]:
            tiers_to_run.append(("Tier 3: Cross-Feature Interactions", "tier3_interactions"))
        if self.tier_filter in ["4", "all"]:
            tiers_to_run.append(("Tier 4: Real-World Scenarios", "tier4_scenarios"))

        for tier_title, tier_folder in tiers_to_run:
            print(f"\n>>> Running {tier_title} ({tier_folder})...")
            modules = self._discover_modules(tier_folder)
            for m in modules:
                m_results = self._load_and_run_module(m, tier_title)
                self.results.extend(m_results)

        total_duration = time.time() - t_start
        passed_count = sum(1 for r in self.results if r.passed)
        failed_count = sum(1 for r in self.results if not r.passed)
        total_count = len(self.results)

        print("\n================================================================================")
        print("                           E2E TEST EXECUTION SUMMARY                           ")
        print("================================================================================")

        # Tier breakdown
        tier_stats: Dict[str, Dict[str, int]] = {}
        for r in self.results:
            if r.tier not in tier_stats:
                tier_stats[r.tier] = {"passed": 0, "failed": 0, "total": 0}
            tier_stats[r.tier]["total"] += 1
            if r.passed:
                tier_stats[r.tier]["passed"] += 1
            else:
                tier_stats[r.tier]["failed"] += 1

        print(f"{'Tier Name':<42} | {'Total':<6} | {'Passed':<6} | {'Failed':<6} | {'Rate':<6}")
        print("-" * 75)
        for t_name, stats in tier_stats.items():
            rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0.0
            print(f"{t_name:<42} | {stats['total']:<6} | {stats['passed']:<6} | {stats['failed']:<6} | {rate:>5.1f}%")

        print("-" * 75)
        print(f"TOTAL TESTS RUN : {total_count}")
        print(f"TOTAL PASSED    : {passed_count}")
        print(f"TOTAL FAILED    : {failed_count}")
        print(f"TOTAL DURATION  : {total_duration:.3f} seconds")
        print("================================================================================")

        if failed_count > 0:
            print("\nFAILURES:")
            for r in self.results:
                if not r.passed:
                    print(f"- {r.tier} :: {r.module} :: {r.name}")
                    print(f"  {r.error}")
            return 1

        print("\n>>> ALL TESTS PASSED! EXIT CODE 0.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Project SAM E2E Test Runner")
    parser.add_argument("--tier", default="all", choices=["1", "2", "3", "4", "all"], help="Filter by tier")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose test reporting")
    args = parser.parse_args()

    runner = SAMTestRunner(verbose=args.verbose, tier_filter=args.tier)
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
