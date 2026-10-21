"""Version-bound human evaluation records; provenance checks, NOT identity authentication."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from .amendments import project_lock, assert_available, atomic_bytes, require, sha
from .state import load_state, persist_state, state_checksum, canonical_json, utc_now, write_json_atomic

CHECKS = ('paper_identity', 'document_version', 'source_location', 'finding_fidelity',
          'study_design', 'numeric_accuracy', 'association_causation', 'null_counter_preservation',
          'scope_limitations', 'evidence_inference')


def digest(value):
    return sha(canonical_json(value).encode())


def requirement(root):
    root = Path(root)
    protocol_path = root / '00_protocol/PROTOCOL.json'
    protocol = json.loads(protocol_path.read_text()) if protocol_path.exists() else {}
    state = load_state(root)
    # A persisted latch prevents deleting a policy or changing a phase flag to evade it.
    return bool(protocol.get('independent_evaluation_policy') or state.get('independent_evaluation_required')
                or (root / '.review/independent-evaluation-required.json').exists())


def _integrity(root):
    state = load_state(root)
    last = json.loads((root / '.review/events.jsonl').read_text().splitlines()[-1])
    require(last['state_sha256'] == state_checksum(last['state']) == state_checksum(state), 'EVALUATION_STATE_JOURNAL_CONFLICT')
    return state


def context(root):
    root = Path(root).resolve()
    assert_available(root)
    state = _integrity(root)
    require(not any(root.glob('*_LAB.json')), 'INDEPENDENT_EVALUATION_OFFICIAL_CORPUS_REQUIRED')
    from .reading.pipeline import ReadingPipeline
    rp = ReadingPipeline(root)
    rp.integrity()
    protocol = rp.context()
    require(protocol.get('status') == 'approved', 'APPROVED_PROTOCOL_REQUIRED')
    result = rp.completion(8)
    require(result['allowed'] and state['phases']['8']['status'] == 'completed',
            'CURRENT_REVIEWED_PHASE8_REQUIRED:' + ';'.join(result['blockers']))
    corpus = rp.corpus()
    evidence = {key: value for key, value in rp.latest('evidence').items() if value['paper_id'] in corpus}
    require(bool(corpus) and bool(evidence), 'NONEMPTY_ELIGIBLE_EVIDENCE_REQUIRED')
    require(protocol.get('example_data') is True or not any(v.get('example_data') for v in evidence.values()),
            'FICTIONAL_EVIDENCE_IN_REAL_EVALUATION')
    sources = {}
    for folder in ('03_library', '04_screening', '05_reading_notes', '06_evidence'):
        for p in (root / folder).rglob('*'):
            require(not p.is_symlink(), 'EVALUATION_SOURCE_SYMLINK')
            if p.is_file():
                sources[str(p.relative_to(root))] = sha(p.read_bytes())
    manifest = {'project_id': state['project_id'], 'protocol_version': protocol['protocol_version'],
                'protocol_sha256': sha((root / '00_protocol/PROTOCOL.json').read_bytes()),
                'eligible_corpus': corpus, 'evidence': evidence,
                'reading_data_sha256': digest(state.get('reading_data', {})), 'source_files': sources}
    return {'contract_version': 'independent-evaluation/1', 'manifest': manifest, 'manifest_sha256': digest(manifest),
            'example_data': protocol.get('example_data', False), 'checks': list(CHECKS),
            'required_method': 'human_source_first', 'identity_authenticated': False,
            'notice': 'Full-corpus independent human checks and per-paper omission review required by this minimal contract; no model or fixture substitutes for real judgment.'}


def validate_record(record, ctx):
    require(isinstance(record, dict), 'EVALUATION_RECORD_OBJECT_REQUIRED')
    require(record.get('contract_version') == 'independent-evaluation/1', 'EVALUATION_CONTRACT_REQUIRED')
    require(record.get('manifest_sha256') == ctx['manifest_sha256'] and record.get('manifest') == ctx['manifest'],
            'EVALUATION_SCOPE_OR_VERSION_STALE')
    require(record.get('example_data') is ctx['example_data'], 'FICTIONAL_EVALUATION_CANNOT_APPROVE_REAL_PROJECT')
    require(record.get('review_method') == 'human_source_first' and record.get('review_status') == 'completed',
            'INDEPENDENT_HUMAN_REVIEW_REQUIRED')
    for field in ('evaluator', 'reviewed_at', 'independence_statement', 'source_first_method',
                  'limitations', 'correction_history', 'human_confirmation_source'):
        require(isinstance(record.get(field), str) and bool(record[field].strip()), 'EVALUATION_FIELD_REQUIRED:' + field)
    require(record.get('confirmation', {}).get('by') not in {None, '', record['evaluator']}
            and record['confirmation'].get('status') == 'accepted'
            and bool(record['confirmation'].get('basis')),
            'SEPARATE_HUMAN_CONFIRMATION_REQUIRED')
    provenance = record.get('source', {})
    require(provenance.get('origin') == 'independent_human' and provenance.get('example_data') is ctx['example_data']
            and bool(provenance.get('description')), 'HUMAN_EVALUATION_SOURCE_REQUIRED')
    items = record.get('items', {})
    evidence = ctx['manifest']['evidence']
    require(set(items) == set(evidence), 'EVALUATION_EVIDENCE_COVERAGE_MISMATCH')
    for eid, value in evidence.items():
        item = items[eid]
        require(item.get('revision_id') == value['revision_id'] and set(item.get('checks', {})) == set(CHECKS),
                'EVALUATION_ITEM_VERSION_OR_CHECKS_MISMATCH:' + eid)
        for name, judgment in item['checks'].items():
            require(judgment.get('verdict') in {'agree', 'not_applicable'} and bool(judgment.get('rationale')),
                    'EVALUATION_UNRESOLVED:' + eid + ':' + name)
            anchors = judgment.get('source_anchor_ids', [])
            require(bool(anchors) and set(anchors) <= set(value['source_anchor_ids']), 'EVALUATION_SOURCE_LOCATION_REQUIRED:' + eid)
    papers = record.get('paper_coverage', {})
    require(set(papers) == set(ctx['manifest']['eligible_corpus']), 'EVALUATION_PAPER_COVERAGE_MISMATCH')
    for pid, row in papers.items():
        require(row.get('document_id') == ctx['manifest']['eligible_corpus'][pid]['document_id']
                and row.get('status') == 'complete' and bool(row.get('omission_review')),
                'EVALUATION_OMISSION_REVIEW_REQUIRED:' + pid)
    require(record.get('unresolved_findings') == [], 'EVALUATION_UNRESOLVED_FINDINGS')


def register(root, record_path, source_path, confirmation_path, human_attestation=False):
    require(human_attestation, 'ACTUAL_HUMAN_ATTESTATION_REQUIRED')
    root = Path(root).resolve()
    with project_lock(root):
        ctx = context(root)
        record = json.loads(Path(record_path).read_text())
        validate_record(record, ctx)
        source, confirmation = Path(source_path).read_bytes(), Path(confirmation_path).read_bytes()
        require(bool(source.strip()) and bool(confirmation.strip()) and sha(source) != sha(confirmation),
                'TWO_DISTINCT_HUMAN_SOURCE_RECORDS_REQUIRED')
        require(record['source'].get('sha256') == sha(source) and
                record['confirmation'].get('source_sha256') == sha(confirmation), 'EVALUATION_SOURCE_CHECKSUM_MISMATCH')
        # Fixed immutable local paths; never trust caller-supplied executable paths or external URLs.
        rid = 'IE-' + uuid.uuid4().hex
        folder = root / '.review/independent-evaluations' / rid
        atomic_bytes(folder / 'evaluator-source', source)
        atomic_bytes(folder / 'confirmation-source', confirmation)
        write_json_atomic(folder / 'record.json', record)
        entry = {'record_id': rid, 'record_path': str((folder / 'record.json').relative_to(root)),
                 'record_sha256': sha((folder / 'record.json').read_bytes()), 'registered_at': utc_now(),
                 'identity_authenticated': False}
        state = load_state(root)
        state.setdefault('independent_evaluations', []).append(entry)
        persist_state(root, state, 'independent_human_evaluation_registered', entry)
        return entry


def gate(root):
    root = Path(root).resolve()
    try:
        if not requirement(root):
            return {'status': 'not_required', 'allowed': True, 'blockers': [], 'identity_authenticated': False,
                    'notice': 'Legacy protocol has no independent-evaluation requirement; no validation claim.'}
        state = _integrity(root)
        entries = state.get('independent_evaluations', [])
        require(bool(entries), 'INDEPENDENT_EVALUATION_MISSING')
        entry = entries[-1]
        events = [json.loads(line) for line in (root / '.review/events.jsonl').read_text().splitlines() if line.strip()]
        require(any(e.get('event') == 'independent_human_evaluation_registered' and e.get('payload') == entry
                    and e.get('state_sha256') == state_checksum(e['state']) for e in events), 'EVALUATION_REGISTRATION_PROVENANCE_MISSING')
        rid = entry['record_id']
        require(isinstance(rid, str) and rid.startswith('IE-') and '/' not in rid and '..' not in rid, 'INVALID_EVALUATION_ID')
        path = root / '.review/independent-evaluations' / rid / 'record.json'
        require(entry['record_path'] == str(path.relative_to(root)) and not any(p.is_symlink() for p in [path, path.parent]),
                'UNSAFE_EVALUATION_PATH')
        require(sha(path.read_bytes()) == entry['record_sha256'], 'EVALUATION_RECORD_CHANGED')
        record = json.loads(path.read_text())
        ctx = context(root)
        validate_record(record, ctx)
        require(not any((path.parent / name).is_symlink() for name in ('evaluator-source', 'confirmation-source')),
                'UNSAFE_EVALUATION_SOURCE_PATH')
        require(record['source']['sha256'] == sha((path.parent / 'evaluator-source').read_bytes())
                and record['confirmation']['source_sha256'] == sha((path.parent / 'confirmation-source').read_bytes()),
                'EVALUATION_SOURCE_CHANGED')
        return {'status': 'pass', 'allowed': True, 'blockers': [], 'record_id': rid, 'identity_authenticated': False,
                'notice': 'Current human-declared records structurally verified; identity, independence and truth are not authenticated by the CLI.'}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return {'status': 'blocked', 'allowed': False, 'blockers': [str(exc)], 'identity_authenticated': False}
