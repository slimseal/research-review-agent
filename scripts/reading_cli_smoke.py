"""Installed-package subprocess checks outside checkout; no human approval or live network."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--with-pdf", action="store_true")
    args = ap.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    logs = []
    def call(command, expected=0):
        cmd = [sys.executable, "-I", "-m", "research_review_agent", *map(str, command)]
        r = subprocess.run(cmd, cwd=out, text=True, capture_output=True)
        logs.append({"command": cmd, "exit_code": r.returncode, "expected": expected, "stdout": r.stdout, "stderr": r.stderr})
        (out / "commands.json").write_text(json.dumps(logs, indent=2))
        assert r.returncode == expected, r.stdout + r.stderr
        return json.loads(r.stdout) if r.stdout.strip() else {"error_text": r.stderr}
    import research_review_agent
    (out / "installed-package.txt").write_text(str(research_review_agent.__file__))
    call(["reading-schema"])
    call(["schema"])
    call(["capabilities"])
    project = out / "official"
    call(["init", "--output", project, "--question", "FICTIONAL installation check, not research", "--domain", "test"])
    call(["phase-context", "--project", project, "--phase", 7])
    call(["phase-context", "--project", project, "--phase", 8])
    call(["evidence-gate", "--project", project], 2)
    call(["reading-context", "--project", project, "--paper-id", "absent", "--document-id", "absent"], 2)
    source = json.loads((args.source / "READING_LAB.json").read_text())
    did = next(iter(source["corpus"].values()))["document_id"]
    pid = next(iter(source["corpus"]))
    lab = out / "lab"
    call(["reading-lab-init", "--project", lab, "--source", args.source, "--question", "Installation-only isolated source check", "--document-ids", did])
    result = call(["document-parse", "--project", lab, "--document-id", did], 0 if args.with_pdf else 2)
    if args.with_pdf:
        ctx = call(["reading-context", "--project", lab, "--paper-id", pid, "--document-id", did])
        anchor = call(["anchor-create", "--project", lab, "--document-id", did, "--pdf-page", 1, "--quote", "DOI: 10.21105/joss.01686"])
        call(["anchor-lookup", "--project", lab, "--anchor-id", anchor["anchor_id"]])
        call(["anchor-confirm", "--project", lab, "--anchor-id", anchor["anchor_id"], "--by", "NOT_A_HUMAN", "--note", "Must be refused in lab"], 2)
        assert ctx["pages"]
    else:
        assert result["error"]["code"] == "PARSER_UNAVAILABLE"
    call(["reading-coverage", "--project", lab])
    call(["reading-queue", "--project", lab])
    call(["evidence-gate", "--project", lab], 2)
    call(["reading-recover", "--project", lab])
    (lab / ".review/state.json").write_text("deliberate isolated recovery test")
    call(["reading-recover", "--project", lab])
    (out / "summary.json").write_text(json.dumps({"checks": len(logs), "passed": True, "with_pdf": args.with_pdf, "human_approvals": 0}, indent=2))
    print(json.dumps({"checks": len(logs), "passed": True, "with_pdf": args.with_pdf}))


if __name__ == "__main__":
    main()
