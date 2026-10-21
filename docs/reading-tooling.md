# Scientific reading and evidence extraction tutorial

Python CLI + packaged workflow procedures are self-contained. Install `pip install 'research-review-agent[pdf]'` (or `pip install -e '.[pdf]'` in a checkout). Visual inspection needs an external PDF viewer/renderer; the development pilot used existing Poppler. No global research Skills or model API key is required by the CLI. Codex/researchers supply interpretation.

## Formal review

Start only after actual upstream approvals and a current Gate 1:

```bash
rragent validate --project reviews/my-review
rragent next --project reviews/my-review
rragent phase-context --project reviews/my-review --phase 7
rragent screening-gate --project reviews/my-review
rragent advance --project reviews/my-review --phase 7 --status in_progress
rragent document-parse --project reviews/my-review --document-id DOCUMENT_ID
rragent reading-context --project reviews/my-review --paper-id PAPER_ID --document-id DOCUMENT_ID
rragent reading-schema
```

Read the full source and inspect layout, then create exact anchors:

```bash
rragent anchor-create --project reviews/my-review --document-id DOCUMENT_ID --pdf-page 2 --quote "Exact text copied from the inspected source"
rragent anchor-lookup --project reviews/my-review --anchor-id ANCHOR_ID
rragent reading-submit --project reviews/my-review --config note.json
rragent reading-inspect --project reviews/my-review --id NOTE_ID
rragent reading-queue --project reviews/my-review
```

The Phase 7 procedure returned by phase-context specifies all note fields. Populate all 25 content fields with present source-grounded text or explicit missing status/reason. Use pages_read, visual_pages, layout_assessment and named section coverage; never infer inspection from parser success.

Stop for genuine human review. Only the researcher, after inspecting source and interpretation, should execute:

```bash
rragent reading-review --project reviews/my-review --id NOTE_ID --action accept --by "Actual reviewer" --comment "Actual review account"
rragent reading-completion --project reviews/my-review
rragent advance --project reviews/my-review --phase 7 --status completed
rragent advance --project reviews/my-review --phase 8 --status in_progress
rragent phase-context --project reviews/my-review --phase 8
```

Create one item JSON per specific finding/argument with source anchors, applicable types and the five support boundaries. The Phase 8 procedure describes the input contract; the CLI generates evidence_id, locator and pending review state.

```bash
rragent evidence-submit --project reviews/my-review --config item.json
rragent evidence-inspect --project reviews/my-review --id EVIDENCE_ID
rragent reading-validate --project reviews/my-review
rragent reading-coverage --project reviews/my-review
```

After real human evidence review and per-paper completeness review:

```bash
rragent evidence-review --project reviews/my-review --id EVIDENCE_ID --action accept --by "Actual reviewer" --comment "Actual review account"
rragent evidence-close --project reviews/my-review --paper-id PAPER_ID --status complete --explanation "Actual coverage review" --by "Actual reviewer"
rragent evidence-gate --project reviews/my-review
rragent advance --project reviews/my-review --phase 8 --status completed
```

Do not run these approval commands merely to make a gate pass. Correction uses --action correct --changes correction.json, retaining the stable ID and requiring acceptance again. Model revisions use stable ID plus current supersedes_revision. Reading corrections stale dependent evidence; evidence corrections stale coverage closure.

## Isolated demonstration

reading-lab-init --project NEW_PATH --source EXISTING_AUTHORIZED_LIBRARY --question QUESTION --document-ids ID1 ID2 copies sources without importing approvals. It cannot be nested in a formal review and cannot approve notes/evidence or complete phases. Reading labs are testing, never a workaround for blocked Gate 1.

examples/round2g-reading/authored-pilot.json contains explicitly labeled, manually authored provisional interpretations of two genuine PDFs, not a generic extraction algorithm or gold standard. scripts/run_reading_pilot.py replays these inputs through the CLI and records command logs. It is not required for ordinary installed use.

## Recovery

Preserve unexpected edits, then reading-recover regenerates projections from the existing workflow journal. Missing PDFs/parses/anchors need lawful source recovery/revalidation, not fabricated reconstruction. One writer per project. Legacy v1 matrices remain unchanged and need a future explicit migration before formal new extraction completion.
