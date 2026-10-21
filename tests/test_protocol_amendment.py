"""Fictional isolated engineering tests. Never approvals of the real pilot."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_review_agent import amendments as a
from research_review_agent.project import initialize_project, update_protocol_draft
from research_review_agent.state import load_state, recover_state, persist_state
from research_review_agent.validation import protocol_status, validate_project
from research_review_agent.workflow import evaluate_gates
from research_review_agent import independent_evaluation as ie

REPO = Path(__file__).resolve().parents[1]


class AmendmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.root = self.base / 'project'
        initialize_project(self.root, 'Fictional original question?', 'test', REPO/'examples/configs/education.json')
        self.source = self.base/'source.json'; self.source.write_text('{"example_data": true, "decision": "Fictional test only"}')
        self.reqpath = self.base/'request.json'
        p = json.loads((self.root/'00_protocol/PROTOCOL.json').read_text())
        self.old = p
        self.req = {'request_id': 'test-amendment', 'expected': {
            'project_id': p['project_id'], 'protocol_version': p['protocol_version'],
            'protocol_sha256': a.sha((self.root/'00_protocol/PROTOCOL.json').read_bytes()),
            'state_sha256': a.sha((self.root/'.review/state.json').read_bytes()),
            'journal_sha256': a.sha((self.root/'.review/events.jsonl').read_bytes()), 'old_question': p['research_question']},
            'new_question': 'Fictional revised question?', 'new_version': '0.3-draft', 'reason': 'FICTIONAL controlled change',
            'source_path': str(self.source), 'source_sha256': a.sha(self.source.read_bytes()),
            'consistency_review': {k: 'FICTIONAL inspected and retained' for k in ('subquestions','concepts','search_plan','screening','extensions')},
            'draft_patch': {'human_decisions': {'resolved': ['D1 FICTIONAL', 'D2 FICTIONAL', 'D3 FICTIONAL', 'D4 FICTIONAL', 'D5 FICTIONAL', 'D6 FICTIONAL deferral'], 'pending': []},
                            'independent_evaluation_policy': {'required_before_phase': 9, 'assignment': 'deferred', 'evaluation_status': 'not_completed'}}}

    def submit(self):
        self.reqpath.write_text(json.dumps(self.req))
        return a.amend_question(self.root, self.reqpath)

    def test_revision_preserves_identity_history_and_decisions(self):
        oldjournal = (self.root/'.review/events.jsonl').read_bytes()
        self.submit()
        p = json.loads((self.root/'00_protocol/PROTOCOL.json').read_text())
        self.assertEqual(p['research_question'], self.req['new_question'])
        self.assertEqual(load_state(self.root)['research_question'], p['research_question'])
        for key in ('project_id','created_at','schema_version','approved_by','approved_at','status'):
            self.assertEqual(p[key], self.old[key])
        self.assertEqual(p['human_decisions'], self.req['draft_patch']['human_decisions'])
        self.assertEqual(p['search'], self.old['search'])
        self.assertEqual(p['screening']['criteria_version'], '0.3-draft')
        self.assertTrue((self.root/'.review/events.jsonl').read_bytes().startswith(oldjournal))
        self.assertTrue((self.root/'.review/protocol-amendments/test-amendment/before/00_protocol/PROTOCOL.json').is_file())
        self.assertTrue(protocol_status(self.root)['pending_human_review'])
        self.assertIn('Independent evaluation policy', (self.root/'00_protocol/REVIEW_PROTOCOL.md').read_text())
        self.assertFalse([i for i in validate_project(self.root, True) if i.severity == 'error'])

    def test_existing_update_still_rejects_rq(self):
        self.reqpath.write_text(json.dumps({'research_question': 'not allowed'}))
        with self.assertRaisesRegex(ValueError, 'protected'):
            update_protocol_draft(self.root, self.reqpath)

    def test_approved_protocol_rejected_without_approval_call(self):
        p = copy.deepcopy(self.old); p['status'] = 'approved'
        (self.root/'00_protocol/PROTOCOL.json').write_text(json.dumps(p))
        with self.assertRaisesRegex(ValueError, 'UNAPPROVED'):
            self.submit()

    def test_downstream_file_rejected(self):
        (self.root/'02_discovery/result.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'DOWNSTREAM_DATA'):
            self.submit()

    def test_downstream_csv_row_rejected(self):
        with (self.root/'03_library/PAPER_REGISTRY.csv').open('a') as f:
            f.write('FICTIONAL-PAPER\n')
        with self.assertRaisesRegex(ValueError, 'DOWNSTREAM_DATA'):
            self.submit()

    def test_downstream_phase_rejected(self):
        s = load_state(self.root); s['phases']['1']['status'] = 'in_progress'
        persist_state(self.root,s,'FICTIONAL_transition')
        with self.assertRaisesRegex(ValueError, 'PHASE0_ONLY'):
            self.submit()

    def test_hash_and_version_conflicts(self):
        for key in ('project_id','protocol_version','protocol_sha256','state_sha256','journal_sha256'):
            original = self.req['expected'][key]; self.req['expected'][key] = 'wrong'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'CONFLICT'):
                self.submit()
            self.req['expected'][key] = original

    def test_source_changed_rejected(self):
        self.source.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
            self.submit()

    def test_consistency_review_required(self):
        del self.req['consistency_review']['search_plan']
        with self.assertRaisesRegex(ValueError, 'CONSISTENCY_REVIEW'):
            self.submit()

    def test_idempotent_replay_no_duplicate_event(self):
        self.submit(); journal = (self.root/'.review/events.jsonl').read_bytes()
        self.assertTrue(self.submit()['replayed'])
        self.assertEqual((self.root/'.review/events.jsonl').read_bytes(), journal)

    def test_same_id_different_request_rejected(self):
        self.submit(); self.req['reason'] = 'different'
        with self.assertRaisesRegex(ValueError, 'REQUEST_ID_CONFLICT'):
            self.submit()

    def test_interrupt_and_recover_at_every_commit_boundary(self):
        # Different isolated fixture per subtest, no real project corruption.
        for point in ('prepared','write:00_protocol/PROTOCOL.json','write:.review/state.json','write:.review/events.jsonl','before_clear'):
            with self.subTest(point=point):
                h = AmendmentTests(); h.setUp()
                try:
                    def interrupt(stage):
                        if stage == point: raise RuntimeError('FICTIONAL interruption')
                    with patch.object(a,'_fault',side_effect=interrupt), self.assertRaisesRegex(RuntimeError,'interruption'):
                        h.submit()
                    with self.assertRaisesRegex(ValueError, 'RECOVERY_REQUIRED'): load_state(h.root)
                    recover_state(h.root)
                    self.assertEqual(load_state(h.root)['research_question'],h.req['new_question'])
                    self.assertTrue(h.submit()['replayed'])
                    self.assertFalse((h.root/a.ACTIVE).exists())
                finally: h.doCleanups()

    def test_recovery_refuses_conflicting_manual_edit(self):
        with patch.object(a,'_fault',side_effect=RuntimeError('stop')), self.assertRaises(RuntimeError): self.submit()
        (self.root/'00_protocol/PROTOCOL.json').write_text('unexpected user edit')
        with self.assertRaisesRegex(ValueError,'RECOVERY_CONFLICT'): recover_state(self.root)

    def test_process_lock_conflict(self):
        code = 'from pathlib import Path; from research_review_agent.amendments import project_lock;\nwith project_lock(Path('+repr(str(self.root))+')): pass'
        with a.project_lock(self.root):
            result = subprocess.run([sys.executable,'-c',code],cwd=REPO,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0); self.assertIn('PROJECT_OPERATION_CONFLICT', result.stderr)

    def test_policy_cannot_be_removed_via_update(self):
        self.submit(); self.reqpath.write_text(json.dumps({'independent_evaluation_policy': {'required_before_phase': None}}))
        with self.assertRaisesRegex(ValueError,'CANNOT_BE_REMOVED'): update_protocol_draft(self.root,self.reqpath)

    def test_missing_evaluation_and_original_gates_block(self):
        self.submit()
        self.assertEqual(ie.gate(self.root)['status'],'blocked')
        self.assertIn('INDEPENDENT_EVALUATION_MISSING',ie.gate(self.root)['blockers'])
        for phase,key in ((7,'gate-1-screening-before-reading'),(12,'gate-3-claims-before-gap'),(15,'gate-2-evidence-before-drafting')):
            gates = evaluate_gates(self.root,phase,True)
            self.assertEqual(gates[key]['status'],'fail')
        for phase in (9,12,15,18):
            self.assertFalse(evaluate_gates(self.root,phase,True)['independent-evaluation-before-synthesis']['assessment']['allowed'])

    def test_stage_flag_or_ordinary_boolean_cannot_release(self):
        self.submit(); s=load_state(self.root)
        s.update(independent_evaluator='Someone',independent_evaluation_approved=True)
        s['phases']['8']['status']='completed'; persist_state(self.root,s,'FICTIONAL flags')
        self.assertFalse(ie.gate(self.root)['allowed'])

    def test_direct_synthesis_and_writing_block(self):
        self.submit()
        from research_review_agent.synthesis.pipeline import SynthesisPipeline
        from research_review_agent.writing.pipeline import WritingPipeline
        for cls in (SynthesisPipeline,WritingPipeline):
            p=cls(self.root)
            self.assertIn('INDEPENDENT_EVALUATION_MISSING',p.upstream())

    def test_no_skills_and_case_neutral(self):
        for name in ('amendments.py','independent_evaluation.py'):
            content=(REPO/'research_review_agent'/name).read_text().lower()
            for phrase in ('social media','political participation','tiktok','instagram','urban green'):
                self.assertNotIn(phrase,content)
        self.assertFalse(list((REPO/'.agents').rglob('SKILL.md')))


def evaluation_fixture():
    """Contract-only FICTIONAL sample; no source-reading accuracy claim."""
    manifest={'project_id':'FICTIONAL-PROJECT','protocol_version':'FICTIONAL', 'eligible_corpus':{'P1':{'document_id':'D1'}},
              'evidence':{'E1':{'revision_id':'R1','source_anchor_ids':['A1']}}}
    ctx={'manifest':manifest,'manifest_sha256':ie.digest(manifest),'example_data':True}
    r={'contract_version':'independent-evaluation/1','manifest':manifest,'manifest_sha256':ctx['manifest_sha256'],
       'example_data':True,'review_method':'human_source_first','review_status':'completed',
       'evaluator':'FICTIONAL evaluator','reviewed_at':'FICTIONAL date','independence_statement':'FICTIONAL independence',
       'source_first_method':'FICTIONAL test','limitations':'FICTIONAL','correction_history':'FICTIONAL none',
       'human_confirmation_source':'FICTIONAL confirmation','confirmation':{'by':'FICTIONAL second reviewer','status':'accepted','basis':'FICTIONAL'},
       'source':{'origin':'independent_human','example_data':True,'description':'FICTIONAL source'},'unresolved_findings':[],
       'items':{'E1':{'revision_id':'R1','checks':{k:{'verdict':'agree','rationale':'FICTIONAL only','source_anchor_ids':['A1']} for k in ie.CHECKS}}},
       'paper_coverage':{'P1':{'document_id':'D1','status':'complete','omission_review':'FICTIONAL only'}}}
    return ctx,r


class EvaluationContractTests(unittest.TestCase):
    def test_complete_contract_only(self):
        ctx,r=evaluation_fixture(); ie.validate_record(r,ctx)

    def test_fixture_cannot_approve_real_context(self):
        ctx,r=evaluation_fixture(); ctx['example_data']=False
        with self.assertRaisesRegex(ValueError,'FICTIONAL'): ie.validate_record(r,ctx)

    def test_copied_project_and_stale_version_rejected(self):
        ctx,r=evaluation_fixture()
        for field in ('project_id','protocol_version'):
            other=copy.deepcopy(ctx); other['manifest'][field]='different'; other['manifest_sha256']=ie.digest(other['manifest'])
            with self.assertRaisesRegex(ValueError,'STALE'): ie.validate_record(r,other)

    def test_model_name_boolean_not_evaluation(self):
        ctx,r=evaluation_fixture()
        for candidate in ({'evaluator':'Somebody','approved':True}, {**r,'review_method':'model_review'}):
            with self.assertRaises(ValueError): ie.validate_record(candidate,ctx)

    def test_missing_judgment_or_location_rejected(self):
        ctx,r=evaluation_fixture(); del r['items']['E1']['checks']['numeric_accuracy']
        with self.assertRaisesRegex(ValueError,'CHECKS'): ie.validate_record(r,ctx)
        ctx,r=evaluation_fixture(); r['items']['E1']['checks']['numeric_accuracy']['source_anchor_ids']=['wrong']
        with self.assertRaisesRegex(ValueError,'LOCATION'): ie.validate_record(r,ctx)

    def test_unresolved_findings_and_omissions_block(self):
        ctx,r=evaluation_fixture(); r['unresolved_findings']=['material error']
        with self.assertRaisesRegex(ValueError,'UNRESOLVED'): ie.validate_record(r,ctx)
        ctx,r=evaluation_fixture(); r['paper_coverage']={}
        with self.assertRaisesRegex(ValueError,'COVERAGE'): ie.validate_record(r,ctx)

    def test_human_attestation_required_before_io(self):
        with self.assertRaisesRegex(ValueError,'ATTESTATION'): ie.register(Path('/unused'),None,None,None)


class EvaluationRegistrationTests(unittest.TestCase):
    """Actual local record I/O with mocked FICTIONAL corpus context, not academic validation."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.root = self.base/'project'
        initialize_project(self.root, 'FICTIONAL registration test?', 'test', REPO/'examples/configs/education.json')
        state = load_state(self.root); state['independent_evaluation_required'] = True
        persist_state(self.root, state, 'FICTIONAL policy')
        self.ctx, self.record = evaluation_fixture()
        self.src = self.base/'source'; self.src.write_text('FICTIONAL evaluator source; not human review')
        self.confirm = self.base/'confirm'; self.confirm.write_text('FICTIONAL confirmation; not human review')
        self.record['source']['sha256'] = a.sha(self.src.read_bytes())
        self.record['confirmation']['source_sha256'] = a.sha(self.confirm.read_bytes())
        self.rp = self.base/'record.json'; self.rp.write_text(json.dumps(self.record))
        self.mock = patch.object(ie, 'context', return_value=self.ctx); self.mock.start(); self.addCleanup(self.mock.stop)

    def register(self):
        return ie.register(self.root,self.rp,self.src,self.confirm,True)

    def test_registered_sources_and_later_context_change(self):
        self.register()
        self.assertEqual(ie.gate(self.root)['status'], 'pass')
        self.assertFalse(ie.gate(self.root)['identity_authenticated'])
        self.ctx['manifest_sha256'] = 'changed-corpus-hash'
        self.assertIn('EVALUATION_SCOPE_OR_VERSION_STALE', ie.gate(self.root)['blockers'])

    def test_source_and_record_tampering_block(self):
        entry = self.register(); folder = (self.root/entry['record_path']).parent
        original = (folder/'evaluator-source').read_bytes()
        (folder/'evaluator-source').write_text('changed')
        self.assertIn('EVALUATION_SOURCE_CHANGED', ie.gate(self.root)['blockers'])
        (folder/'evaluator-source').write_bytes(original)
        (folder/'record.json').write_text('{}')
        self.assertIn('EVALUATION_RECORD_CHANGED', ie.gate(self.root)['blockers'])

    def test_declarative_registration_without_event_rejected(self):
        entry = self.register(); state = load_state(self.root)
        state['independent_evaluations'][-1] = {**entry, 'registered_at': 'invented'}
        persist_state(self.root, state, 'FICTIONAL ordinary state edit')
        self.assertIn('EVALUATION_REGISTRATION_PROVENANCE_MISSING', ie.gate(self.root)['blockers'])

    def test_registration_wrong_source_checksum_rejected(self):
        self.src.write_text('different source')
        with self.assertRaisesRegex(ValueError, 'SOURCE_CHECKSUM'):
            self.register()
        self.assertFalse(load_state(self.root).get('independent_evaluations'))


if __name__=='__main__': unittest.main()
