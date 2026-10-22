# Installation

Start with the [Beginner Quick Start](beginner-quick-start.md) if you do not use a terminal.
Ask Codex to explain and perform these local setup steps with your permission.
For a fixed version, download the source ZIP from the
[v1.1-experimental pre-release](https://github.com/slimseal/research-review-agent/releases/tag/v1.1-experimental).
The project uses [MIT](../LICENSE); third-party rights remain separate. The package
version is still `0.1.0.dev0`, not PyPI 1.1. No binary installer is supplied.

## Requirements

- Python 3.11 or later.
- A working Codex environment for the natural-language experience (the Python controller can also be used by technical users without Codex).
- Git is recommended for development but is not required to run the local controller.

The core CLI and scholarly adapters have no third-party runtime dependency and no dependency on global or personal Codex Skills. Building from source uses the declared `setuptools>=68` PEP 517 backend.

There is no separate model SDK or model API key required by this package. Codex's
own account/access requirements are separate. Metadata planning and core commands
work without PDF extras or optional provider keys.

## Local install (macOS/Linux)

After downloading and extracting the intended revision, open its root in Codex.
If using Git instead of ZIP, the optional download commands are:

```bash
git clone https://github.com/slimseal/research-review-agent.git
cd research-review-agent
```

From the extracted/cloned project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
rragent --help
rragent provider-status
```

On Windows PowerShell, create with `py -3 -m venv .venv`, then activate with
`.venv\Scripts\Activate.ps1` and run the same `python -m pip ...` command. Windows
instructions are provided but this release acceptance was run on macOS, not Windows.
Installation may download the declared build backend; it does not search literature.
Beginners do not need to run the regression suite to start a review.

Keep pip's default build isolation for a normal online installation: it obtains the
declared build backend automatically. Do not add `--no-build-isolation` as a beginner
workaround. That advanced option is appropriate only when a compatible local backend
is already installed; fully offline installation is not promised.

## Run without installing

From the repository root:

```bash
python3 -m research_review_agent --help
python3 -m research_review_agent init --question "..." --output reviews/my-review
python3 -m research_review_agent next --project reviews/my-review
```

Registry and procedure resources are included in the Python package, so an installed CLI can load them outside the source directory.

## Optional provider configuration

Do not configure every provider before starting. The local control plane and offline
planning need no key. Crossref, PubMed, Europe PMC, ERIC, arXiv and OpenAIRE returned
anonymous metadata in saved tests. OpenAlex/Semantic Scholar are implemented but their
latest test requests failed due to quota/rate limits. See [database access](database-access.md)
for endpoint-specific setup and [capability observations](../README.md#actual-implementation-and-observed-access).
Only configure a key when the chosen operation needs it; these are placeholders, not credentials:

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

## Maintainer verification (optional for users)

With the PDF extra and the virtual environment active, run `bash scripts/run_tests.sh`.
The suite uses offline fixtures; it does not certify live provider availability or
scientific correctness. The earlier offline/no-build-isolation attempt failed because
that environment lacked `setuptools.build_meta`; this was not a demonstrated package bug.
The subsequent [final release gate](V1_1_FINAL_RELEASE_GATE.md) passed normal online
installation in two new virtual environments without system/user packages: editable
core and regular installation with the PDF extra. Both ran the documented CLI and
planning commands outside the source directory. Tested on macOS / Python 3.13.2;
other platforms/Python versions and fully offline installation were not verified.
