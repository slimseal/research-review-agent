"""Installed-package CLI smoke, outside the checkout, no skills or API calls.

Uses an isolated copy of a user-selected upstream corpus. All recommendations are
explicit test-operation uncertainty, NOT academic judgments or human reviews.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    for name in ("python", "source", "output", "criteria", "pdf", "authorization"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expect-missing-parser", action="store_true")
    a = parser.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    root = a.output / "lab"
    results = []
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
    def call(argv, expected=0, project=True):
        command = [str(a.python), "-I", "-m", "research_review_agent", *argv]
        if project:
            command += ["--project", str(root)]
        r = subprocess.run(command, cwd=a.output, env=env, capture_output=True, text=True)
        results.append({"command": command, "expected_exit": expected, "actual_exit": r.returncode, "stdout": r.stdout, "stderr": r.stderr})
        (a.output / "commands.json").write_text(json.dumps(results, indent=2))
        if r.returncode != expected:
            raise AssertionError(results[-1])
        return json.loads(r.stdout) if r.stdout else {}
    location = subprocess.run([str(a.python), "-I", "-c", "import research_review_agent; print(research_review_agent.__file__)"], cwd=a.output, capture_output=True, text=True, check=True)
    (a.output / "installed-package.txt").write_text(location.stdout)
    call(["screening-schema"], project=False)
    official = a.output / "unapproved-review"
    call(["init", "--question", "Fictional portability Protocol question", "--output", str(official)], project=False)
    call(["next", "--project", str(official)], project=False)
    context = call(["phase-context", "--project", str(official), "--phase", "6"], project=False)
    assert "screening-context" in context["procedure"]
    call(["screening-lab-init", "--source", str(a.source), "--question", "Isolated CLI verification only; no academic judgment or approval"])
    call(["screening-criteria", "--config", str(a.criteria), "--reason", "CLI smoke only"])
    call(["screening-criteria-approve", "--by", "TEST_ONLY", "--note", "Must reject lab approval"], expected=2)
    latest = None
    for stage in ("title", "abstract", "fulltext_eligibility"):
        args = ["screening-context", "--paper-id", "P0000001", "--stage", stage]
        if stage == "fulltext_eligibility":
            imported = call(["document-import", "--paper-id", "P0000001", "--file", str(a.pdf), "--authorization", str(a.authorization), "--version-kind", "version_of_record"], expected=2 if a.expect_missing_parser else 0)
            if a.expect_missing_parser:
                assert imported["error"]["code"] == "PARSER_UNAVAILABLE"
            else:
                doc = imported["document"]
                args += ["--document-id", doc["document_id"], "--pages", "1"]
                call(["document-parse", "--document-id", doc["document_id"]], expected=2)
        packet = call(args)
        proposal = {"packet_id": packet["packet_id"], "decision": "uncertain", "reason_codes": ["insufficient_information"],
                    "explanation": "CLI smoke only; no academic assessment performed", "criteria_ids": ["I-tool", "E-application"], "source_facts": []}
        path = a.output / (stage + ".json")
        path.write_text(json.dumps(proposal))
        latest = call(["screening-propose", "--config", str(path)])
        replay = call(["screening-propose", "--config", str(path)])
        assert latest["decision_id"] == replay["decision_id"]
    call(["screening-review", "--decision-id", latest["decision_id"], "--action", "approve", "--by", "TEST_ONLY", "--note", "Must not approve pilot"], expected=2)
    call(["screening-inspect", "--decision-id", latest["decision_id"]])
    call(["acquisition-status", "--export"])
    for name in ("screening-status", "screening-queue", "screening-exclusions", "screening-coverage", "acquisition-status", "screening-validate", "documents-validate"):
        call([name])
    call(["screening-gate"], expected=2)
    # Recovery of a disposable smoke lab only; no source corpus is changed.
    (root / ".review/state.json").write_text("simulated interrupted write")
    call(["screening-recover"])
    call(["recover"])
    call(["screening-validate"])
    call(["screening-gate"], expected=2)
    print(json.dumps({"checks": len(results), "all_expected": True, "installed_package": location.stdout.strip(), "output": str(a.output)}))


if __name__ == "__main__":
    main()
