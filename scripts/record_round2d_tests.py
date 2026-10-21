"""Capture reproducible local validation logs; no network, no live pilot."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--shell", action="store_true", help="Run the repository's required bash regression entry point")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    commands = [
        [sys.executable, "-m", "compileall", "-q", "research_review_agent", "workflow", "tests", "scripts"],
        [sys.executable, "scripts/validate_workflow.py"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    ]
    summary = []
    if args.shell:
        commands[-1] = ["bash", "scripts/run_tests.sh"]
    environment = dict(os.environ)
    environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")
    for index, command in enumerate(commands):
        result = subprocess.run(command, cwd=repo, capture_output=True, text=True, env=environment)
        log = args.output / f"{index+1:02d}.log"
        log.write_text(result.stdout + result.stderr)
        summary.append({"command": command, "exit_code": result.returncode, "log": str(log), "tail": (result.stdout + result.stderr).splitlines()[-5:]})
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if all(r["exit_code"] == 0 for r in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
