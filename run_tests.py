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

    # Run only fast unit tests
    python run_tests.py --unit-only

    # Verbose output
    python run_tests.py -v
"""

import sys
import subprocess
import argparse


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
    
    # Run tests
    exit_code = run_tests(args)
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
