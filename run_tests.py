#!/usr/bin/env python3
# run_tests.py
"""
Test runner script for AlphaLens unit tests.

Usage:
    # Run all tests
    python run_tests.py

    # Run specific agent tests
    python run_tests.py --agent financial
    python run_tests.py --agent scorer
    python run_tests.py --agent red_flag
    python run_tests.py --agent news
    python run_tests.py --agent rag
    python run_tests.py --agent orchestration

    # Run with coverage
    python run_tests.py --coverage

    # Run benchmark-style AI evaluation
    python run_tests.py --eval

    # Run only fast unit tests
    python run_tests.py --unit-only

    # Verbose output
    python run_tests.py -v
"""

import asyncio
import json
import sys
import subprocess
import argparse
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_EVAL_BENCHMARK = ROOT_DIR / "tests" / "fixtures" / "alphalens_eval_benchmark.json"


class _FakeSession:
    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def close(self):
        return None


async def _fake_get_session():
    yield _FakeSession()


def _load_eval_benchmark(benchmark_path: Path) -> dict:
    with benchmark_path.open("r", encoding="utf-8") as file_handle:
        benchmark = json.load(file_handle)

    if not benchmark.get("cases"):
        raise ValueError(f"Benchmark file has no cases: {benchmark_path}")

    return benchmark


def _compare_value(actual, expected, path: str):
    issues = []

    if isinstance(expected, dict) and any(key in expected for key in ("min", "max", "equals", "contains")):
        if "min" in expected and actual < expected["min"]:
            issues.append(f"{path}: expected >= {expected['min']}, got {actual}")
        if "max" in expected and actual > expected["max"]:
            issues.append(f"{path}: expected <= {expected['max']}, got {actual}")
        if "equals" in expected and actual != expected["equals"]:
            issues.append(f"{path}: expected {expected['equals']}, got {actual}")
        if "contains" in expected and expected["contains"] not in str(actual):
            issues.append(f"{path}: expected to contain {expected['contains']!r}, got {actual!r}")
        return issues

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected dict, got {type(actual).__name__}"]

        for key, expected_value in expected.items():
            if key not in actual:
                issues.append(f"{path}.{key}: missing")
                continue
            issues.extend(_compare_value(actual[key], expected_value, f"{path}.{key}"))
        return issues

    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected list, got {type(actual).__name__}"]
        if len(actual) != len(expected):
            issues.append(f"{path}: expected length {len(expected)}, got {len(actual)}")
        for index, expected_item in enumerate(expected):
            if index < len(actual):
                issues.extend(_compare_value(actual[index], expected_item, f"{path}[{index}]"))
        return issues

    if actual != expected:
        issues.append(f"{path}: expected {expected!r}, got {actual!r}")

    return issues


async def _run_eval_case(case: dict) -> dict:
    """Run a single benchmark case through the orchestrator with mocked agent outputs."""
    from src.orchestration import run_analysis

    fake_financial = {
        "ticker": case["ticker"],
        "financial_data": case["financial_data"],
        "error": None,
        "stored": True,
        "yahoo": "success",
        "fmp": "success",
    }
    fake_scores = {
        "ticker": case["ticker"],
        **case["scores"],
        "error": None,
    }
    fake_red_flags = {
        "ticker": case["ticker"],
        **case["red_flags"],
        "error": None,
    }
    fake_news = {
        "ticker": case["ticker"],
        "articles": case["news_sentiment"].get("articles", []),
        "sentiment_summary": case["news_sentiment"]["sentiment_summary"],
        "error": None,
    }

    with ExitStack() as stack:
        stack.enter_context(patch("src.dbo.database.get_session", _fake_get_session))
        stack.enter_context(patch("src.orchestration.nodes.fetch_and_store_financials", new=AsyncMock(return_value=fake_financial)))
        stack.enter_context(patch("src.orchestration.nodes.score_company", new=AsyncMock(return_value=fake_scores)))
        stack.enter_context(patch("src.orchestration.nodes.detect_red_flags", new=AsyncMock(return_value=fake_red_flags)))
        stack.enter_context(patch("src.orchestration.nodes.analyze_news", new=AsyncMock(return_value=fake_news)))

        result = await run_analysis(
            case["ticker"],
            run_name=f"Eval {case['ticker']}",
            trace_tags=["eval", case["id"]],
            trace_metadata={
                "eval_case_id": case["id"],
                "eval_kind": "benchmark",
            },
        )

    return result


async def run_eval(args):
    """Run the benchmark-style AI evaluation flow."""
    benchmark_path = Path(args.eval_benchmark).expanduser().resolve()
    benchmark = _load_eval_benchmark(benchmark_path)

    print(f"Running AlphaLens benchmark eval: {benchmark.get('name', benchmark_path.name)}")
    print(f"Benchmark file: {benchmark_path}")
    print("=" * 70)

    case_results = []
    passed_cases = 0

    for case in benchmark["cases"]:
        print(f"\n▶ Case {case['id']} ({case['ticker']})")
        result = await _run_eval_case(case)

        checks = []
        checks.extend(_compare_value(result.get("workflow_status"), case["expected"]["workflow_status"], "workflow_status"))
        checks.extend(_compare_value(result.get("recommendation"), case["expected"]["recommendation"], "recommendation"))
        checks.extend(_compare_value(result.get("confidence"), case["expected"]["confidence"], "confidence"))
        checks.extend(_compare_value(result.get("scores", {}), case["expected"]["scores"], "scores"))
        checks.extend(_compare_value(result.get("red_flags", {}), case["expected"]["red_flags"], "red_flags"))
        checks.extend(_compare_value(result.get("news_sentiment", {}), case["expected"]["news_sentiment"], "news_sentiment"))

        passed = len(checks) == 0
        if passed:
            passed_cases += 1
            print("  ✅ PASS")
        else:
            print("  ❌ FAIL")
            for issue in checks:
                print(f"     - {issue}")

        case_results.append(
            {
                "id": case["id"],
                "ticker": case["ticker"],
                "passed": passed,
                "checks": checks,
                "result": result,
            }
        )

    total_cases = len(case_results)
    failed_cases = total_cases - passed_cases
    pass_rate = (passed_cases / total_cases * 100) if total_cases else 0.0

    print("\n" + "=" * 70)
    print("Eval summary")
    print(f"Cases: {total_cases}")
    print(f"Passed: {passed_cases}")
    print(f"Failed: {failed_cases}")
    print(f"Pass rate: {pass_rate:.1f}%")

    if failed_cases:
        print("\nFailures:")
        for case_result in case_results:
            if case_result["passed"]:
                continue
            print(f"- {case_result['id']} ({case_result['ticker']}): {len(case_result['checks'])} issue(s)")

    return 0 if failed_cases == 0 else 1


def run_tests(args):
    """Run pytest with specified options."""
    cmd = ["pytest"]
    
    # Add verbosity
    if args.verbose:
        cmd.append("-vv")
    else:
        cmd.append("-v")
    
    # Add coverage
    if args.coverage:
        cmd.extend(["--cov=src", "--cov-report=html", "--cov-report=term"])
    
    # Filter by agent
    if args.agent:
        agent_map = {
            'financial': 'tests/agents/test_financial_agent.py',
            'scorer': 'tests/agents/test_scorer_agent.py',
            'red_flag': 'tests/agents/test_red_flag_agent.py',
            'news': 'tests/agents/test_news_agent.py',
            'rag': 'tests/agents/test_rag_agent.py',
            'orchestration': 'tests/orchestration/test_orchestration.py',
        }
        
        if args.agent in agent_map:
            cmd.append(agent_map[args.agent])
        else:
            print(f"Unknown agent: {args.agent}")
            print(f"Available: {', '.join(agent_map.keys())}")
            sys.exit(1)
    
    # Filter by marker
    if args.unit_only:
        cmd.extend(["-m", "unit"])
    
    if args.marker:
        cmd.extend(["-m", args.marker])
    
    # Run specific test
    if args.test:
        cmd.extend(["-k", args.test])
    
    # Show failures instantly
    if args.fail_fast:
        cmd.append("-x")
    
    # Print command
    print(f"Running: {' '.join(cmd)}")
    print("=" * 70)
    
    # Run pytest
    result = subprocess.run(cmd)
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Run AlphaLens unit tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        '--agent',
        choices=['financial', 'scorer', 'red_flag', 'news', 'rag', 'orchestration'],
        help='Run tests for specific agent',
    )
    
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Generate coverage report',
    )

    parser.add_argument(
        '--eval',
        action='store_true',
        help='Run the benchmark-style AI evaluation instead of pytest',
    )

    parser.add_argument(
        '--eval-benchmark',
        default=str(DEFAULT_EVAL_BENCHMARK),
        help='Path to the benchmark JSON file used by --eval',
    )
    
    parser.add_argument(
        '--unit-only',
        action='store_true',
        help='Run only fast unit tests',
    )
    
    parser.add_argument(
        '-m', '--marker',
        help='Run tests with specific marker (e.g., slow, integration)',
    )
    
    parser.add_argument(
        '-k', '--test',
        help='Run specific test by name pattern',
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output',
    )
    
    parser.add_argument(
        '-x', '--fail-fast',
        action='store_true',
        help='Stop on first failure',
    )
    
    args = parser.parse_args()
    
    # Run tests or eval
    if args.eval:
        exit_code = asyncio.run(run_eval(args))
    else:
        exit_code = run_tests(args)
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
