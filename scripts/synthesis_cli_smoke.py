"""Fresh installed-package checks, -I isolation, no network or human approval."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--with-pdf", action="store_true")
    args = ap.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    logs = []
    def call(command, expected=0):
        cmd = [sys.executable, "-I", "-m", "research_review_agent", *map(str, command)]
        run = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
        logs.append({"command": cmd, "exit_code": run.returncode, "expected": expected, "stdout": run.stdout, "stderr": run.stderr})
        (out / "commands.json").write_text(json.dumps(logs, indent=2))
        assert run.returncode == expected, run.stdout + run.stderr
        return json.loads(run.stdout) if run.stdout.strip() else {"error_text": run.stderr}
    import research_review_agent
    (out / "installed-package.txt").write_text(str(research_review_agent.__file__))
    call(["synthesis-schema"])
    call(["capabilities"])
    official = out / "unapproved"
    call(["init", "--output", official, "--question", "FICTIONAL installation check only"])
    for phase in (9, 10, 11, 12):
        context = call(["phase-context", "--project", official, "--phase", phase])
        assert not context["allowed_to_start"]
    call(["synthesis-completion", "--project", official], 2)
    call(["advance", "--project", official, "--phase", 12, "--status", "in_progress"], 2)
    lab = out / "isolated"
    if not args.with_pdf:
        result = call(["synthesis-lab-init", "--project", lab, "--source", args.source], 2)
        assert "PARSER_UNAVAILABLE" in json.dumps(result)
    else:
        runner = Path(__file__).with_name("run_synthesis_pilot.py")
        run = subprocess.run([sys.executable, "-I", str(runner), "--project", str(lab), "--source", str(args.source), "--plan", str(args.plan)], cwd=out, capture_output=True, text=True)
        (out / "pilot-replay.log").write_text(run.stdout + run.stderr)
        assert run.returncode == 0, run.stdout + run.stderr
        context = call(["synthesis-context", "--project", lab])
        claim = next(v for v in context["records"] if v["kind"] == "claim")
        call(["synthesis-inspect", "--project", lab, "--id", claim["record_id"]])
        call(["synthesis-validate", "--project", lab])
        call(["synthesis-completion", "--project", lab, "--phase", 12], 2)
        call(["synthesis-review", "--project", lab, "--id", claim["record_id"], "--action", "approve", "--by", "NOT_A_HUMAN", "--rationale", "Must be rejected in isolated lab"], 2)
        projection = lab / "08_argument/CLAIM_MAP.csv"
        projection.write_text("FICTIONAL recovery corruption")
        call(["synthesis-validate", "--project", lab], 2)
        projection.with_suffix(".preserved-edit.txt").write_bytes(projection.read_bytes())
        (lab / ".review/state.json").write_text("FICTIONAL deliberate corrupt state")
        call(["synthesis-recover", "--project", lab])
        call(["synthesis-inspect", "--project", lab, "--id", claim["record_id"]])
    summary = {"cli_checks": len(logs), "passed": True, "with_pdf": args.with_pdf, "human_approvals": 0,
               "notice": "Replay of authored interpretations, not independent semantic validation."}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
