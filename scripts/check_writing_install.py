"""Run from outside the checkout with a fresh installed interpreter; all mutations are isolated copies."""
import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
import research_review_agent
from research_review_agent.state import write_json_atomic

p = argparse.ArgumentParser()
p.add_argument("--output", type=Path, required=True)
p.add_argument("--fictional", type=Path, required=True)
p.add_argument("--real", type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise ValueError("NEW_INSTALL_CHECK_OUTPUT_REQUIRED")
a.output.mkdir(parents=True)
module_path = str(Path(research_review_agent.__file__).resolve())
if "site-packages" not in module_path:
    raise ValueError("NOT_TESTING_INSTALLED_PACKAGE:" + module_path)
has_pdf = bool(importlib.util.find_spec("pypdf"))
results = []
def run(command, args=(), expected=0):
    argv = [sys.executable, "-m", "research_review_agent", command, *map(str, args)]
    r = subprocess.run(argv, cwd=a.output, text=True, capture_output=True)
    results.append({"argv": argv, "exit_code": r.returncode, "expected": expected, "stdout": r.stdout, "stderr": r.stderr})
    write_json_atomic(a.output / "commands.json", results)
    if r.returncode != expected:
        raise ValueError(r.stdout + r.stderr)
    return json.loads(r.stdout)
run("writing-schema")
run("capabilities")
blank = a.output / "blank"
run("init", ("--question", "How should independently dated material assemblages be interpreted?", "--output", blank, "--domain", "archaeology"))
run("phase-context", ("--project", blank, "--phase", "13"))
run("writing-completion", ("--project", blank, "--phase", "18"), 2)
run("recover", ("--project", blank))
real = a.output / "real-copy"
shutil.copytree(a.real, real)
if not has_pdf:
    result = run("writing-validate", ("--project", real), 2)
    if "PARSER_UNAVAILABLE" not in json.dumps(result):
        raise ValueError("MISSING_PDF_DEPENDENCY_NOT_EXPLICIT")
else:
    fictional = a.output / "fictional-copy"
    shutil.copytree(a.fictional, fictional)
    run("writing-context", ("--project", fictional))
    run("writing-validate", ("--project", fictional))
    run("writing-completion", ("--project", fictional, "--phase", "18"))
    for phase in (7, 12, 15):
        run("gate", ("--project", fictional, "--phase", str(phase), "--allow-example-data"))
    (fictional / ".review/state.json").write_text("INTENTIONALLY CORRUPTED ISOLATED TEST COPY")
    run("writing-recover", ("--project", fictional))
    run("writing-completion", ("--project", fictional, "--phase", "18"))
    from research_review_agent.writing.pipeline import WritingPipeline
    pipe = WritingPipeline(real)
    span = next(iter(pipe.current_spans().values()))
    run("writing-trace", ("--project", real, "--id", span["span_id"]))
    run("writing-impact", ("--project", real, "--id", span["evidence_ids"][0]))
    run("writing-bibliography", ("--project", real))
    run("writing-report", ("--project", real))
    run("writing-completion", ("--project", real, "--phase", "18"), 2)
    run("writing-audit-context", ("--project", real, "--auditor", "Fresh install interface test", "--context-id", "install-test-no-semantic-verdict"))
write_json_atomic(a.output / "result.json", {"installed_module": module_path, "pdf_extra": has_pdf, "commands": len(results), "all_expected_exits": True,
                  "notice": "Test copies only. No new human or semantic audit assertions."})
print(json.dumps({"commands": len(results), "pdf_extra": has_pdf, "installed_module": module_path}))
