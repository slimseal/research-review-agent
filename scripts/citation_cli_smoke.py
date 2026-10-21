"""Fresh-installed package test. FICTIONAL data only; no network. Run Python -I."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from research_review_agent.citations.pipeline import CitationPipeline
from research_review_agent.citations.providers import CitationProviders
from research_review_agent.scholarly.contracts import PaperCandidate
from research_review_agent.scholarly.registry import PaperRegistry
from research_review_agent.scholarly.transport import HttpResponse
from research_review_agent.state import write_json_atomic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    root = parser.parse_args().output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    logs = []
    def cli(*args, expected=0):
        result = subprocess.run([sys.executable, "-I", "-m", "research_review_agent", *map(str, args)], cwd=root, capture_output=True, text=True)
        logs.append({"args": list(map(str, args)), "exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        write_json_atomic(root / "CLI_RESULTS.json", logs)
        assert result.returncode == expected, logs[-1]
        return json.loads(result.stdout) if result.stdout.strip() else {"stderr": result.stderr}
    review = root / "review"
    cli("init", "--question", "Fictional fresh-install test only", "--output", review)
    cli("validate", "--project", review)
    cli("phase-context", "--project", review, "--phase", 4)
    cli("next", "--project", review)
    cli("citation-expand", "--project", review, "--provider", "crossref", "--direction", "backward", expected=2)
    cli("provider-status")
    cli("capabilities")
    lab = root / "lab"
    cli("citation-lab-init", "--project", lab)
    c = PaperCandidate("fixture", "fictional-seed", "fixture", "2099-01-01T00:00:00Z", "fixture", 0,
                       "Fictional portability seed", ["Fixture Author"], 2099, None, "10.5555/fictional.portability", None, None, "unknown", None)
    sid = PaperRegistry(lab).register(c).paper_id
    config = root / "seeds.json"
    write_json_atomic(config, {"selected_paper_ids": [sid], "selection_reason": {sid: "Fictional software test only"}, "provider_plan": [{"provider": "crossref", "direction": "backward"}]})
    cli("citation-seeds", "--project", lab)
    cli("citation-seed-register", "--project", lab, "--config", config, "--by", "fixture")
    cli("citation-seed-approve", "--project", lab, "--by", "fixture", "--note", "Fictional pilot only", "--pilot-selection")
    class FixtureTransport:
        def get(self, **kwargs):
            body = json.dumps({"message": {"DOI": c.doi, "reference": [{"DOI": c.doi}, {"unstructured": "Fictional unresolved reference"}]}}).encode()
            return HttpResponse(200, {}, body, kwargs["url"])
    pipeline = CitationPipeline(lab, CitationProviders(FixtureTransport()))
    run = pipeline.start("crossref", "backward")
    assert run["discovered_count"] == 2 and run["unresolved_count"] == 1
    cli("citation-status", "--project", lab)
    cli("citation-unresolved", "--project", lab)
    cli("citations-validate", "--project", lab)
    cli("citation-replay", "--project", lab, "--run-id", run["expansion_run_id"])
    cli("citation-resume", "--project", lab, "--run-id", run["expansion_run_id"])
    (lab / ".review/state.json").write_text("intentional fictional test corruption")
    cli("citations-recover", "--project", lab)
    cli("citations-validate", "--project", lab)
    cli("citation-report", "--project", lab, "--completion", expected=2)
    print(json.dumps({"passed_cli_commands": len(logs), "mocked_pipeline": "passed", "log": str(root / "CLI_RESULTS.json")}, indent=2))


if __name__ == "__main__":
    main()
