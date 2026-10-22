# V1.1 Experimental — Final Release Gate

Date: 2026-10-22. Branch: `codex/v1.1-database-access`.

**Historical verification record:** the checks below predate publication. The owner
subsequently authorized MIT licensing and GitHub publication; current licensing is
in [LICENSE](../LICENSE) and current distribution notes are in [Release Notes](V1_1_RELEASE_NOTES.md).
Statements below about pending licensing/publication describe that earlier checkpoint.

**Result: normal first-install and basic-command gate passed.** No implementation,
packaging configuration, workflow or test fix was necessary. The candidate is ready
for an owner-authorized local Experimental source commit with the documented limits.
No commit, merge, push, tag, Release or license addition was performed.

## Independent installation evidence

The complete proposed source set (324 files at test start, including all uncommitted
Batch 1–2 and Scholar work) was copied into a brand-new temporary directory. No Git
ignored virtual environment, private project, PDF, cache or log was copied.

Two separate virtual environments were created using system Python 3.13.2 on macOS:

- `include-system-site-packages = false`; user site disabled.
- Before installation each environment contained **pip only**. No development-package
  directory, user packages, PYTHONPATH, provider keys or global Skills were inherited.
- pip configuration was disabled for the test; public PyPI was explicitly selected,
  caches disabled, retries disabled, with bounded timeouts. Network was used only
  for the declared installation dependencies, not scholarly operations.

| Installation | Actual outcome |
|---|---|
| `python -m pip install -e .` | Passed with default online build isolation; editable wheel built and installed. |
| `python -m pip install '.[pdf]'` in a second new environment | Passed; normal wheel built and installed with pinned pypdf 6.20.1. |
| `python -m pip check` | Passed; no broken requirements. |

The regular installation imported the package from its own virtual environment's
site-packages, not the source checkout or original development environment. The
editable installation resolved to the new source copy, as intended.

## Beginner commands actually executed

Each of these exited 0 in **both** installed environments, from outside the source directory:

1. `rragent --help`
2. `rragent capabilities`
3. `rragent provider-status` (offline; no probes)
4. `rragent source-plan` with an education RQ/domain and a new output file
5. `rragent init` into a new temporary research folder
6. `rragent next`
7. `rragent phase-context --phase 0`
8. `rragent scholar-prepare` using an Agent-authored three-query input
9. `rragent literature-coverage`

The RQ concerned first-year teachers and classroom authority. No papers were invented
or imported. Scholar remained **not_performed**; zero candidate observations, zero
Registry imports, no SearchRuns. No scientific approval, full-text reading or phase
advancement was performed. Provider configuration success is not live connectivity.

The beginner guide correctly delegates JSON/commands to Codex. The installed CLI
accepts the documented arguments. Standard/Comprehensive remain planning conventions,
not nonexistent CLI flags. The PDF dependency install is not a new PDF accuracy test.

## Failure classification and retained limits

The previous offline attempt omitted build isolation while lacking setuptools.
Normal pip installation now fetched the declared build backend and succeeded without
source changes: **environment/build-dependency limitation, not an observed packaging
configuration or application-code failure**. Fully offline installation is not promised.

This checks fresh environments on one existing macOS machine with Python 3.13.2,
not every supported OS/Python version, GUI onboarding usability or a new laptop.
The previously passed 436-test scientific regression suite was not repeated because
no implementation/test changed in this final gate. Its earlier results remain separate.

Scholar automatic completed/incomplete assessment and candidate import remain absent;
provider access limits, whole-plan budget coordination and scientific review limitations
remain in [Known Issues](KNOWN_ISSUES.md). They are disclosed Experimental limitations,
not reasons to develop new features in this release gate. No claim of a fully
academically validated systematic-review system is made.

## Version, files and publication boundary

README, Release Notes and package metadata agree: **V1.1 Experimental** is the product
milestone; `pyproject.toml` and `research_review_agent.__version__` remain **0.1.0.dev0**.
No PyPI version 1.1 or unperformed version bump is claimed. A GitHub milestone/tag
name can differ if this distinction remains explicit.

Only documentation is updated in the original checkout. The final candidate contains
325 source/documentation/test files; installation logs, environments and the exact
candidate-file manifest remain in the private temporary verification directory.
No license is selected; do not advertise an open-source license grant. Public visibility
does not resolve licensing or third-party rights. Existing scientific Gates and private
research workspaces are preserved.

Final checks: 65 local documentation links and `git diff --check` passed. Candidate
files contain no matched private paths/identities, credential patterns, PDFs, logs,
approval JSONL or files over 1 MB; the existing privacy scanner's generic path-prefix
literal is a documented benign match. This bounded scan is not an absolute security guarantee.
Implementation/test/Workflow content hashes match the pre-check baseline. Across
11,657 private pilot files, the path/size/mtime manifest is unchanged, as is the
selected Protocol/state/Registry/Coverage content-hash manifest. Large historical
logs were not individually rehashed. Git HEAD/index remain unchanged.

## Recommended sequence — not executed

1. Owner confirms the reviewed file list and local commit authorization.
2. Stage only that reviewed list; inspect `git diff --cached --stat` and
   `git diff --cached --check`; commit on `codex/v1.1-database-access` with:
   `Prepare Research Review Agent V1.1 Experimental`.
3. After separate remote authorization, recheck remote state/visibility, push the
   feature branch without force, and review its diff before any main merge.
4. Only after owner confirmation of the target commit, limitations, visibility and
   license wording, select a tag (for example `v1.1-experimental`) and create a
   GitHub **prerelease** using the reviewed Release Notes. Do not attach private
   research data or temporary verification logs. License selection may remain pending,
   but the release must not be called open-source licensed.

This document recommends a source snapshot workflow, not an automatically executed release.
