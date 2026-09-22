#!/usr/bin/env python3
"""Project test runner for CSCEC UI automation."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent


def _load_env_file() -> None:
    env_file = PROJECT_DIR / ".env"
    if not env_file.exists():
        env_file = PROJECT_DIR / ".env.example"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _project_python() -> str:
    if sys.platform == "win32":
        python_path = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        python_path = PROJECT_DIR / ".venv" / "bin" / "python"
    if python_path.exists():
        return str(python_path)
    return sys.executable


def _normalize_test_path(path_value: str | None) -> str:
    if not path_value:
        return "tests"
    path = Path(path_value)
    if path.parts and path.parts[0].lower() == "tests":
        return str(path)
    return str(Path("tests") / path)


def _run(cmd: list[str]) -> int:
    print("\nRunning: " + " ".join(cmd) + "\n")
    return subprocess.run(cmd, cwd=PROJECT_DIR).returncode


def _prepare_allure_results(*, keep_existing: bool) -> None:
    """Start a run with a bounded Allure result set unless history is requested."""
    results_dir = PROJECT_DIR / "reports" / "allure-results"
    if results_dir.exists() and not keep_existing:
        shutil.rmtree(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)


def main() -> None:
    _load_env_file()

    parser = argparse.ArgumentParser(
        description="CSCEC UI automation test runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py --env uat --refresh-auth -m smoke
  python run_tests.py --env prod --dry-run
  python run_tests.py --env prod --prod-suite mandatory
  python run_tests.py --env prod -m "write or destructive"
  python run_tests.py --env pre -p console -k service
        """,
    )

    parser.add_argument("-m", "--mark", help="Pytest marker expression")
    parser.add_argument("-p", "--path", help="Test path under tests/, or a full tests/... path")
    parser.add_argument("-k", "--keyword", help="Pytest keyword expression")
    parser.add_argument("--parallel", "-n", action="store_true", help="Run with pytest-xdist")
    parser.add_argument("--reruns", type=int, default=0, help="Retry failed tests")
    parser.add_argument("--headless", dest="headless", action="store_true", help="Run browser headless")
    parser.add_argument("--headed", dest="headless", action="store_false", help="Run browser headed")
    parser.set_defaults(headless=None)
    parser.add_argument("--report", action="store_true", help="Generate Allure report after a passing run")
    parser.add_argument("--html-path", help="Write an additional self-contained HTML report to this path")
    parser.add_argument("--allure-dir", help="Write Allure result files to this directory")
    parser.add_argument(
        "--keep-allure-results",
        action="store_true",
        help="Keep existing reports/allure-results instead of cleaning it before the run",
    )
    parser.add_argument("--no-html", action="store_true", help="Disable pytest-html defaults")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose pytest output")
    parser.add_argument("--env", choices=["uat", "pre", "prod"], help="Target environment")
    parser.add_argument(
        "--prod-suite",
        choices=["mandatory", "conditional", "probe", "controlled-write"],
        help="Select one production execution-responsibility suite",
    )
    parser.add_argument("--dry-run", action="store_true", help="Collect tests without executing them")
    parser.add_argument("--refresh-auth", action="store_true", help="Force login and rewrite auth_states/<env>.json")
    parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Arguments after this flag are passed directly to pytest",
    )

    args = parser.parse_args()

    if args.env:
        os.environ["ENV"] = args.env
    if args.headless is not None:
        os.environ["HEADLESS"] = "true" if args.headless else "false"

    target_env = os.environ.get("ENV", "uat").lower()
    if args.prod_suite and target_env != "prod":
        parser.error("--prod-suite can only be used with --env prod")
    if args.prod_suite and args.mark:
        parser.error("--prod-suite and --mark cannot be used together")

    explicit_selection = bool(args.mark or args.path or args.keyword or args.prod_suite)

    cmd = [_project_python(), "-m", "pytest", _normalize_test_path(args.path)]

    prod_suite_marks = {
        "mandatory": "prod_mandatory and readonly",
        "conditional": "prod_conditional and readonly",
        "probe": "prod_probe and readonly",
        "controlled-write": "controlled_write and (write or destructive)",
    }
    if args.prod_suite:
        cmd.extend(["-m", prod_suite_marks[args.prod_suite]])
    elif args.mark:
        cmd.extend(["-m", args.mark])
    elif target_env == "prod" and not explicit_selection:
        cmd.extend(["-m", "smoke and readonly"])

    if args.keyword:
        cmd.extend(["-k", args.keyword])
    if args.verbose:
        cmd.append("-v")
    if args.parallel:
        cmd.extend(["-n", "auto"])
    if args.reruns > 0:
        cmd.extend(["--reruns", str(args.reruns), "--reruns-delay", "3"])
    if args.no_html:
        cmd.extend(["--no-header", "--tb=short"])
    if args.html_path:
        cmd.extend(["--html", args.html_path, "--self-contained-html"])
    if args.allure_dir:
        cmd.append(f"--alluredir={args.allure_dir}")
    if args.dry_run:
        cmd.append("--collect-only")
    if args.refresh_auth:
        cmd.append("--refresh-auth")
    cmd.extend(args.pytest_args)

    print(f"ENV={target_env}")
    print(f"HEADLESS={os.environ.get('HEADLESS', '')}")
    if target_env == "prod" and not explicit_selection:
        print("Default prod selection: -m \"smoke and readonly\"")
    if args.prod_suite:
        print(f"Production responsibility suite: {args.prod_suite}")

    _prepare_allure_results(keep_existing=args.keep_allure_results)
    exit_code = _run(cmd)

    if args.report and exit_code == 0:
        allure_cmd = [
            "allure",
            "generate",
            "reports/allure-results",
            "-o",
            "reports/allure-report",
            "--clean",
        ]
        _run(allure_cmd)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
