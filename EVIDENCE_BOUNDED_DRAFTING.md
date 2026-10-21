# Evidence-Bounded Drafting

Formal Phase 15 requires active Phase 15, complete reviewed predecessors, valid Phase 8 evidence, current synthesis/claims/gaps, and approved outline/briefs. Normal workflow checks retain all three hard Gates. A populated CSV, placeholder draft or lab cannot substitute for approvals.

Codex drafts one section from `writing-context --section ID`. Inspect sources before wording; use only the protocol, permitted claims/links, evidence, registry, approved maps/gaps and the brief. Preserve numbers and uncertainty, contrary/null evidence, causal versus associational interpretation, proposed versus tested mechanisms, historical/material inference and secondary versus inspected primary sources.

Draft input contains `section_id`, `writer`, `writer_context_id`, `example_data`, and ordered spans. Every span has `text`, classification, claim_ids, evidence_ids and citation_keys. Citations use `[@P0000001]` syntax. A substantive span requires all three reference lists; unresolved/transition spans require a justification. Text is generated solely by joining these spans, so an untracked body cannot be appended through the API.

Supporting/counter/qualifying brief evidence must appear in the section's trace. This is **coverage**, not proof that the prose represents it fairly. All spans require independent source-grounded semantic review before final approval. A small transition heuristic flags obvious factual wording; it cannot reliably detect all disguised claims.

Revise through `writing-submit`, not Markdown editing. Supply the prior record_id, supersedes_version and existing span_id for retained/revised spans; remove output-only audit status fields. New spans receive new IDs. Old versions remain in WRITING_HISTORY and the event journal. Unsupported wording must be weakened, removed or explicitly unresolved; never filled from memory.

The real-source pilot deliberately stores labeled adversarial audit input, not accepted academic conclusions. It remains a non-approvable lab. Production drafting must not reuse those probes.
