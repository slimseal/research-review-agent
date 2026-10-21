# Seed selection and expansion policy

Use protocol relevance, foundational/recent/theoretical/methodological/empirical roles and source diversity; citation frequency alone is insufficient. Each selected canonical Paper Registry ID needs a reason and selector. Missing, conflicting and unknown identities are ineligible. Recommendations have no approval effect.

Register → pending human review → named human approval → bounded operations → stopping/coverage review → explicit Phase 4 transition. No command automatically approves the Protocol, selects a next-round seed, screens a paper or completes a phase. The infrastructure pilot exception has its own marker and `pilot_selected` status and cannot approve Phase 4.

Plans explicitly list provider/direction pairs. Crossref backward, OpenAlex forward and OpenCitations backward/forward are available. Related suggestions are optional/deferred. Explain omitted directions or failed paths during review. Seed replacements/extensions create a new version; old runs remain auditable and are marked stale relative to the current selection. Changes in Protocol content, even without version-string changes, stale the plan. Identity-title/DOI changes also require re-selection/review.

Depth is 1–10, requests 1–1000 per numbered round and candidate observations 1–10000. Defaults 1/30/100. All provider runs and seed versions share that round's consumed budget. Every request has one attempt; manually resume only when appropriate. Failed, timeout and rate-limited requests consume reservations. No automatic recursion or retrying another provider after quota exhaustion.

Later rounds require a prior round and explicit invocation. Researchers can select newly registered identities via a newly reviewed seed version, but never via automatic citation-count ranking. The system does not increase a consumed round's cap; use a documented later plan/round or accept the limitation.

Stopping reasons distinguish low-yield suggestion, quota exhaustion, missing coverage, imposed cap, human stop and completed planned paths. Low additional yield cannot prove saturation. Empty provider results cannot prove no citations. Human review must cover unresolved endpoints, version ambiguity, network biases, incomplete paths, raw unprocessed records and scope/time/language bias.

Official completion requires current seed approval, valid substantive approved Protocol, valid completed Phase 3, every planned path attempted or explicitly limited, intact provenance/exports and a named human review bound to a snapshot hash. Failed paths may be accepted transparently, not hidden. The tool records reviewer assertions; human identity authentication is not implemented. AGENTS forbids the agent from self-signing these records. Any new run or seed/graph mutation invalidates the review hash.
