"""Narrow Phase-0 amendment transaction. No approval or downstream migration."""
from __future__ import annotations

import base64
import copy
import csv
import hashlib
import io
import json
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from .state import canonical_json, state_checksum, utc_now, write_json_atomic

ACTIVE = '.review/amendment-pending.json'
_HELD = set()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


@contextmanager
def project_lock(root):
    """OS advisory lock released on process death. All project CLI operations use it."""
    root = Path(root).resolve()
    owner = (root, threading.get_ident())
    if owner in _HELD:
        yield
        return
    path = root / '.review/operation.lock'
    require(path.parent.is_dir(), 'PROJECT_REQUIRED')
    require(not path.is_symlink(), 'UNSAFE_LOCK_PATH')
    with path.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError('PROJECT_OPERATION_CONFLICT') from exc
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError('PROJECT_OPERATION_CONFLICT') from exc
        _HELD.add(owner)
        try:
            yield
        finally:
            _HELD.remove(owner)
            if os.name == 'nt':
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def assert_available(root):
    require(not (Path(root) / ACTIVE).exists(), 'PROTOCOL_AMENDMENT_RECOVERY_REQUIRED: run recover')


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _encoded(data):
    return {'sha256': sha(data), 'base64': base64.b64encode(data).decode()}


def _decode(entry):
    data = base64.b64decode(entry['base64'], validate=True)
    require(sha(data) == entry['sha256'], 'AMENDMENT_SNAPSHOT_CHECKSUM_MISMATCH')
    return data


def _path(root, relative):
    p = root / relative
    require(not Path(relative).is_absolute() and '..' not in Path(relative).parts,
            'UNSAFE_AMENDMENT_PATH')
    require(not any(x.is_symlink() for x in [p, *p.parents] if x != root.parent), 'SYMLINK_NOT_SUPPORTED')
    return p


def _fault(stage):
    """Test seam; never enabled by an environment variable or CLI switch."""


def recover_amendment(root):
    root = Path(root).resolve()
    with project_lock(root):
        marker = root / ACTIVE
        if not marker.exists():
            return None
        pointer = json.loads(marker.read_text())
        transaction = _path(root, pointer['transaction'])
        data = transaction.read_bytes()
        require(sha(data) == pointer['sha256'], 'AMENDMENT_TRANSACTION_CHANGED')
        tx = json.loads(data)
        # Refuse conflicting human edits; never silently overwrite a third state.
        for relative, value in tx['files'].items():
            p = _path(root, relative)
            current = sha(p.read_bytes()) if p.exists() else None
            require(current in {value['old']['sha256'] if value['old'] else None, value['new']['sha256']},
                    'AMENDMENT_RECOVERY_CONFLICT:' + relative)
            _decode(value['new'])
        for relative, value in tx['files'].items():
            atomic_bytes(_path(root, relative), _decode(value['new']))
            _fault('write:' + relative)
        write_json_atomic(transaction.parent / 'result.json', tx['result'])
        _fault('before_clear')
        marker.unlink()
        return tx['result']


def _phase0(root, protocol, state):
    require(protocol.get('status') == 'draft' and protocol.get('approved_at') is None
            and protocol.get('approved_by') is None, 'UNAPPROVED_DRAFT_REQUIRED')
    require(state['phases']['0']['status'] in {'pending', 'in_progress', 'blocked'}
            and all(state['phases'][str(i)]['status'] == 'pending' for i in range(1, 19)), 'PHASE0_ONLY')
    require(protocol['project_id'] == state['project_id'] and protocol['research_question'] == state['research_question'],
            'PROTOCOL_STATE_IDENTITY_MISMATCH')
    from .constants import INITIAL_CSV_FILES, csv_fields_for_version
    fields = csv_fields_for_version(protocol['schema_version'])
    # Exact empty scaffold only. Unknown nonempty downstream files also fail closed.
    for directory in root.iterdir():
        if not re.match(r'^(0[1-9]|10)_', directory.name) or not directory.is_dir():
            continue
        for p in directory.rglob('*'):
            require(not p.is_symlink(), 'SYMLINK_NOT_SUPPORTED')
            if not p.is_file() or not p.stat().st_size:
                continue
            rel = str(p.relative_to(root))
            require(rel in INITIAL_CSV_FILES, 'DOWNSTREAM_DATA_PRESENT:' + rel)
            rows = list(csv.reader(io.StringIO(p.read_text())))
            require(rows == [fields[INITIAL_CSV_FILES[rel]]], 'DOWNSTREAM_DATA_PRESENT:' + rel)
    require(not any(k.endswith('_data') and v for k, v in state.items()), 'DOWNSTREAM_STATE_PRESENT')
    require(not any(root.glob('*_LAB.json')), 'OFFICIAL_PHASE0_PROJECT_REQUIRED')
    events = [json.loads(line) for line in (root / '.review/events.jsonl').read_text().splitlines() if line.strip()]
    require(events and all(e['state_sha256'] == state_checksum(e['state']) for e in events), 'JOURNAL_INVALID')
    require(events[-1]['state_sha256'] == state_checksum(state), 'STATE_JOURNAL_CONFLICT')
    for e in events:
        require(e['event'] != 'protocol_approved' and
                all(e['state']['phases'][str(i)]['status'] == 'pending' for i in range(1, 19)),
                'DOWNSTREAM_OR_APPROVAL_HISTORY_PRESENT')


def amend_question(root, request_path):
    root = Path(root).resolve()
    request = json.loads(Path(request_path).read_text())
    with project_lock(root):
        rid = request.get('request_id', '')
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', rid), 'INVALID_AMENDMENT_REQUEST_ID')
        txdir = root / '.review/protocol-amendments' / rid
        transaction = txdir / 'transaction.json'
        request_hash = sha(canonical_json(request).encode())
        if transaction.exists():
            tx = json.loads(transaction.read_text())
            require(tx['request_hash'] == request_hash, 'AMENDMENT_REQUEST_ID_CONFLICT')
            if (root / ACTIVE).exists():
                pointer = json.loads((root / ACTIVE).read_text())
                require(pointer['transaction'] == str(transaction.relative_to(root)), 'OTHER_AMENDMENT_PENDING')
                return recover_amendment(root)
            if (txdir / 'result.json').exists():
                # No rewrite on replay, even after subsequent legitimate work.
                return {**tx['result'], 'replayed': True}
        assert_available(root)
        from .state import load_state, render_task_state
        from .project import render_protocol_artifacts, _deep_merge, _validate_extension_definition
        from .validation import validate_protocol
        protocol_path = root / '00_protocol/PROTOCOL.json'
        protocol = json.loads(protocol_path.read_text())
        state = load_state(root)
        _phase0(root, protocol, state)
        checks = {'project_id': protocol['project_id'], 'protocol_version': protocol['protocol_version'],
                  'protocol_sha256': sha(protocol_path.read_bytes()),
                  'state_sha256': sha((root / '.review/state.json').read_bytes()),
                  'journal_sha256': sha((root / '.review/events.jsonl').read_bytes()),
                  'old_question': protocol['research_question']}
        require(request.get('expected') == checks, 'AMENDMENT_VERSION_OR_HASH_CONFLICT')
        question = request.get('new_question')
        require(isinstance(question, str) and question.strip() == question and bool(question)
                and question != checks['old_question'], 'NEW_EXACT_QUESTION_REQUIRED')
        version = request.get('new_version', '')
        require(re.fullmatch(r'\d+(?:\.\d+)+-draft', version) and
                tuple(map(int, version[:-6].split('.'))) > tuple(map(int, protocol['protocol_version'].removesuffix('-draft').split('.'))),
                'INCREASING_DRAFT_VERSION_REQUIRED')
        require(isinstance(request.get('reason'), str) and request['reason'].strip(), 'AMENDMENT_REASON_REQUIRED')
        source = Path(request['source_path']).resolve().read_bytes()
        require(sha(source) == request['source_sha256'] and source.strip(), 'DECISION_SOURCE_CHANGED')
        review = request.get('consistency_review', {})
        require(all(isinstance(review.get(k), str) and review[k].strip() for k in
                    ('subquestions', 'concepts', 'search_plan', 'screening', 'extensions')), 'CONSISTENCY_REVIEW_REQUIRED')
        patch = request.get('draft_patch', {})
        allowed = {'human_decisions', 'boundary_provenance', 'decision_provenance', 'evaluation_checkpoint_note',
                   'independent_evaluation_policy', 'subquestions', 'concept_definitions', 'concept_blocks'}
        require(set(patch) <= allowed, 'AMENDMENT_PATCH_FIELD_NOT_ALLOWED')
        updated = _deep_merge(protocol, patch)
        updated.update(research_question=question, protocol_version=version)
        updated['screening']['criteria_version'] = version
        _validate_extension_definition(updated['evidence_extensions'])
        newstate = copy.deepcopy(state)
        newstate['research_question'] = question
        if updated.get('independent_evaluation_policy', {}).get('required_before_phase') == 9:
            newstate['independent_evaluation_required'] = True
        # Persistent requirement cannot be disabled by a later amendment.
        require(not state.get('independent_evaluation_required') or
                updated.get('independent_evaluation_policy', {}).get('required_before_phase') == 9,
                'INDEPENDENT_EVALUATION_REQUIREMENT_CANNOT_BE_REMOVED')
        newstate.update(seq=state['seq'] + 1, updated_at=utc_now())
        payload = {'request_id': rid, 'old_question': checks['old_question'], 'new_question': question,
                   'old_version': checks['protocol_version'], 'new_version': version,
                   'reason': request['reason'], 'source_sha256': sha(source), 'request_sha256': request_hash}
        event = {'seq': newstate['seq'], 'timestamp': newstate['updated_at'], 'event': 'protocol_question_amended',
                 'payload': payload, 'state': newstate, 'state_sha256': state_checksum(newstate)}
        # Stage and validate every projection before touching canonical files.
        with tempfile.TemporaryDirectory(prefix='rra-amendment-stage-') as temporary:
            stage = Path(temporary); (stage / '00_protocol').mkdir()
            render_protocol_artifacts(stage, updated); render_task_state(stage, newstate)
            errors = [i.message for i in validate_protocol(stage, require_substantive=True) if i.severity == 'error']
            require(not errors, 'AMENDMENT_INVALID_PROTOCOL:' + ';'.join(errors))
            newfiles = {str(p.relative_to(stage)): p.read_bytes() for p in stage.rglob('*') if p.is_file()}
        newfiles['.review/state.json'] = (json.dumps(newstate, ensure_ascii=False, indent=2) + '\n').encode()
        if newstate.get('independent_evaluation_required'):
            newfiles['.review/independent-evaluation-required.json'] = (json.dumps({
                'project_id': protocol['project_id'], 'required_before_phase': 9, 'request_id': rid}) + '\n').encode()
        newfiles['.review/events.jsonl'] = (root / '.review/events.jsonl').read_bytes() + (canonical_json(event) + '\n').encode()
        decisions = (root / 'DECISIONS.md').read_text()
        decisions += ('\n## Controlled RQ amendment ' + rid + '\n\n' +
                      json.dumps(payload, ensure_ascii=False, indent=2) +
                      '\n\nSource receipt and request preserved in `.review/protocol-amendments/' + rid +
                      '/`. Draft only; no signature, approval or phase advancement.\n\nConsistency review:\n' +
                      json.dumps(review, ensure_ascii=False, indent=2) + '\n\nRegistered decisions:\n' +
                      json.dumps(updated['human_decisions'], ensure_ascii=False, indent=2) +
                      '\n\nIndependent evaluation policy (not an evaluation result):\n' +
                      json.dumps(updated.get('independent_evaluation_policy', {}), ensure_ascii=False, indent=2) + '\n')
        newfiles['DECISIONS.md'] = decisions.encode()
        result = {'status': 'draft_amended', **payload, 'project_id': protocol['project_id'], 'approved': False}
        tx = {'request_hash': request_hash, 'result': result, 'files': {rel: {
            'old': _encoded((root / rel).read_bytes()) if (root / rel).exists() else None,
            'new': _encoded(data)} for rel, data in newfiles.items()}}
        txdir.mkdir(parents=True, exist_ok=True)
        for rel, value in tx['files'].items():
            if value['old']:
                atomic_bytes(txdir / 'before' / rel, _decode(value['old']))
        atomic_bytes(txdir / 'source-receipt', source)
        write_json_atomic(txdir / 'request.json', request)
        write_json_atomic(transaction, tx)
        write_json_atomic(root / ACTIVE, {'transaction': str(transaction.relative_to(root)), 'sha256': sha(transaction.read_bytes())})
        _fault('prepared')
        return recover_amendment(root)
