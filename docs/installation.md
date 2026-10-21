# Installation

Round 2I writing/audit commands ship with the same core package: `rragent writing-schema` requires no model SDK or Skill. Existing PDF-backed source checking still requires the declared `pdf` extra. See [writing tooling](writing-tooling.md) for outline/brief submissions, draft tracing, bibliography, independent audit and genuine-human QC. An absent parser yields `PARSER_UNAVAILABLE`, not a substitute interpretation.

## Requirements

- Python 3.11 or later.
- Codex is optional but useful for academic reasoning under `AGENTS.md` and the registered procedures.
- Git is recommended for development but is not required to run the local controller.

The core CLI and scholarly adapters have no third-party runtime dependency and no dependency on global or personal Codex Skills. Building from source uses the declared `setuptools>=68` PEP 517 backend.

Round 2H packages the synthesis contracts, CLI and Phase 9–12 procedures. `rragent synthesis-schema` works in the dependency-free core. Checking existing PDF-backed evidence still requires the existing `pdf` extra; missing parsing dependencies are reported, never replaced with model memory. No additional research library or model API is installed. See [synthesis tooling](synthesis-tooling.md).

Screening instructions, contracts, CLI and tests are packaged locally. Title/abstract screening requires no extra library or API key. Targeted PDF eligibility requires the existing `pdf` extra (`pypdf==6.20.1`); it reports `PARSER_UNAVAILABLE` instead of substituting model memory. See [screening tooling](screening-tooling.md) for the human review boundary and [known issues](KNOWN_ISSUES.md) for the validation scope of this experimental snapshot.

## Editable development install

```bash
git clone https://github.com/slimseal/research-review-agent.git
cd research-review-agent
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --no-deps -e .
rragent schema
bash scripts/run_tests.sh
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

If build isolation would attempt a network download, add `--no-build-isolation` after confirming a compatible local `setuptools` is installed.

## Run without installing

From the repository root:

```bash
python3 -m research_review_agent --help
python3 -m research_review_agent init --question "..." --output reviews/my-review
python3 -m research_review_agent next --project reviews/my-review
```

Registry and procedure resources are included in the Python package, so an installed CLI can load them outside the source directory.

## Optional provider configuration

The local control plane and offline tests require no API key. OpenAlex/Crossref metadata and Crossref/OpenAlex/OpenCitations citation adapters are packaged:

```bash
# Configure your own authorized key when required by the provider/operation.
export OPENALEX_API_KEY='...'

# Optional but recommended for Crossref polite-pool identification
export CROSSREF_MAILTO='you@example.org'

# Optional only for Crossref Metadata Plus subscribers
export CROSSREF_PLUS_API_TOKEN='...'

# Optional OpenCitations access token; never created or purchased automatically
export OPENCITATIONS_ACCESS_TOKEN='...'

rragent provider-status
```

Export values through your shell credential mechanism; never commit them. The package does not automatically load `.env` files. `provider-status` reports configured/not-configured booleans, not connectivity or successful API access.

Authorized public-link acquisition/local import are packaged. Install the optional parser with `python -m pip install -e '.[pdf]'`: pinned `pypdf==6.20.1`, BSD-3-Clause. No OCR, AES decryption, image extraction or third-party research Skills are installed. Without this extra core workflow/metadata/citation commands still work, while PDF operations fail explicitly. Round 2G reading/extraction contracts and CLI are packaged; interpretation requires Codex/researcher execution of bundled procedures, not another SDK or global Skill. Visual PDF inspection needs a viewer/renderer (the pilot used existing Poppler). OCR, robust table recognition and related-paper recommendations remain unavailable. See [reading tooling](reading-tooling.md).

Publisher or subscription access must use a user-authorized session. The workflow never bypasses access controls.
