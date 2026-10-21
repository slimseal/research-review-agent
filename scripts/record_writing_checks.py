"""Record real CLI behavior on an isolated writing lab; never signs or advances it."""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from research_review_agent.state import write_json_atomic
from research_review_agent.writing.pipeline import WritingPipeline

p = argparse.ArgumentParser()
p.add_argument("--project", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--response", type=Path)
p.add_argument("--correct", action="store_true")
a = p.parse_args()
if a.output.exists():
    raise ValueError("NEW_EXECUTION_LOG_REQUIRED")
a.output.mkdir(parents=True)
calls = []
def run(command, extra=(), config=None, expected=0):
    argv = [sys.executable, "-m", "research_review_agent", command, "--project", str(a.project), *extra]
    if config is not None:
        path = a.output / f"{len(calls):03d}-input.json"
        write_json_atomic(path, config)
        argv += ["--config", str(path)]
    result = subprocess.run(argv, capture_output=True, text=True)
    calls.append({"argv": argv, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
    write_json_atomic(a.output / "commands.json", calls)
    if result.returncode != expected:
        raise ValueError(result.stdout + result.stderr)
    return json.loads(result.stdout)

pipe = WritingPipeline(a.project)
if not pipe.lab:
    raise ValueError("THIS_RUNNER_ONLY_SUPPORTS_NON_APPROVABLE_LABS")
if a.response:
    context = pipe.data["audit_contexts"][-1]
    run("writing-audit-submit", ("--id", context["audit_id"]), json.loads(a.response.read_text()))
if a.correct:
    for draft in pipe.latest("draft").values():
        cfg = copy.deepcopy(draft)
        cfg["supersedes_version"] = draft["version"]
        cfg["example_data"] = False
        cfg["spans"] = [s for s in cfg["spans"] if s.get("evaluation_role") != "adversarial_not_a_finding"]
        for s in cfg["spans"]:
            for key in ("source_verification_status", "semantic_review_status", "audit_status"):
                s.pop(key, None)
            s["text"] = s["text"].replace("values as cells", "one value per cell")
        run("writing-submit", ("--kind", "draft"), cfg)
    run("writing-bibliography")
    context = run("writing-audit-context", ("--auditor", "Codex fresh-context auditor", "--context-id", "round2i-source-audit-2"))
    write_json_atomic(a.output / "audit-request.json", context)
run("writing-validate")
pipe = WritingPipeline(a.project)
span = next(iter(pipe.current_spans().values()))
run("writing-trace", ("--id", span["span_id"]))
run("writing-impact", ("--id", span["evidence_ids"][0]))
run("writing-report")
run("writing-completion", ("--phase", "18"), expected=2)
print(json.dumps({"calls": len(calls), "log": str(a.output)}))
