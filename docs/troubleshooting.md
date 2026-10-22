# Common beginner problems

| Symptom | What it means / safe next step |
|---|---|
| `scholar-prepare` or `source-plan` is missing | Check the downloaded revision. Before V1.1 publication, GitHub main contains V1. Ask Codex to inspect local `--help`; do not pretend the command ran. |
| Python or `rragent` not found | Follow [installation](installation.md); activate the local virtual environment. From the source root, `python -m research_review_agent --help` avoids executable-path ambiguity. |
| Dependency installation fails | Preserve the error; confirm network/Python/build-backend availability. Do not install arbitrary substitutes or report success. |
| `not_verified` provider | Offline configuration is known, current endpoint access is not. A real probe requires authorization and budget. |
| `key_missing` / `key_invalid` | Check the specific operation. Optional keys do not block unrelated providers. Keep values private; do not paste credentials into issue reports. |
| OpenAlex quota check gives 401 | The keyed quota endpoint and anonymous search are distinct. Do not infer all endpoints are unavailable or automatically switch credential modes. |
| `quota_exhausted` / HTTP 429 | Preserve quota/rate-limit evidence. No hidden retries, purchases or fallback. Other authorized sources may continue. |
| Institutional database unavailable | A subscription is not necessarily API entitlement; Scopus/WoS/PsycINFO adapters are not implemented here. Keep the coverage gap explicit. |
| Scholar `not_performed` | No valid user session records exist. Generated queries are not searches. |
| Scholar `performed_as_reported` | Some valid user-reported work exists; this is **not** `completed`. Review unchecked query IDs and actual ranges. Scope completion remains not_assessed. |
| Scholar `invalid_records` | Fix the reporting inconsistency against real notes while preserving old versions. Do not invent a session or force a success label. |
| Manual candidate absent from Registry | Expected: automatic Scholar import is unsupported. Keep not_imported; separately authorized DOI reconciliation is a different network operation. |
| Workflow/Gate blocked | Read `next` / `phase-context`, underlying artifacts and missing human reviews. Do not edit phase flags or use a lab to bypass research approval. |
| PDF/table number looks wrong | Inspect the actual page or retain uncertainty. NUL/minus extraction and table limitations are known; do not guess. |
| Bibliography or writing validation fails | Preserve the error; existing duplicate-title bibliography limitation remains. A writing sample is not final QC approval. |

Send only redacted errors when seeking help. Never upload PDFs, raw private research
logs, approval identities, credentials or private local paths. See [Known Issues](KNOWN_ISSUES.md).
