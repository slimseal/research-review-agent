"""Execute explicit, externally authored assessments through CLI. Never generate judgments.

Use only a SCREENING_LAB for development. Every command/input/output is retained.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--assessments", required=True, type=Path)
    args = parser.parse_args()
    root = args.project.resolve()
    if not (root / "SCREENING_LAB.json").exists():
        raise ValueError("This demonstration runner must not operate an official review")
    output = root / "pilot_execution" / args.assessments.stem
    output.mkdir(parents=True, exist_ok=False)
    logs = []
    def call(command):
        result = subprocess.run([sys.executable, "-m", "research_review_agent", *command, "--project", str(root)], capture_output=True, text=True)
        logs.append({"argv": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        (output / "commands.json").write_text(json.dumps(logs, ensure_ascii=False, indent=2))
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return json.loads(result.stdout)
    for item in json.loads(args.assessments.read_text())["assessments"]:
        command = ["screening-context", "--paper-id", item["paper_id"], "--stage", item["stage"]]
        if item.get("document_id"):
            command += ["--document-id", item["document_id"], "--pages", *map(str, item["pages"])]
        context = call(command)
        facts = item.get("source_facts", [])
        if item["stage"] == "title":
            facts = [{"location": "title", "quote": context["basic_metadata"]["title"]}]
        data = {"packet_id": context["packet_id"], "decision": item["decision"], "review_role": item.get("review_role"),
                "reason_codes": item.get("reason_codes", ["criterion_not_met" if item["decision"] == "exclude" else "potentially_relevant" if item["decision"] == "include" else "insufficient_information"]),
                "explanation": item["explanation"], "reviewer_id": "Codex / Round2F provisional pilot",
                "criteria_ids": item.get("criteria_ids", ["I-tool", "E-application"]), "source_facts": facts,
                "uncertainty_flags": item.get("uncertainty_flags", ["no_actual_human_review", "unapproved_pilot_scope"])}
        if item.get("superseded_decision_id"):
            data["superseded_decision_id"] = item["superseded_decision_id"]
        path = output / (item["paper_id"] + "-" + item["stage"] + ".json")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        call(["screening-propose", "--config", str(path)])
    print(json.dumps({"assessments": len(logs)//2, "logs": str(output / "commands.json"), "human_reviews": 0}))


if __name__ == "__main__":
    main()
