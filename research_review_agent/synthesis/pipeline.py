from __future__ import annotations

import copy
import csv
import io
import json
import os
import shutil
import tempfile
import uuid
from functools import wraps
from pathlib import Path

from ..documents.parser import checksum
from ..documents.store import atomic_blob, digest, safe_path
from ..reading.pipeline import ReadingPipeline, read
from ..reading.contracts import require, nonempty
from ..state import load_state, new_state, persist_state, recover_state, state_checksum, utc_now, write_json_atomic
from .contracts import VERSION, PHASE, MAPS, ACTIONS, validate_record, validate_semantics

PATHS = {"theme": "07_synthesis/THEME_MAP.md", "theory": "07_synthesis/THEORY_MAP.md",
         "method": "07_synthesis/METHOD_MAP.md", "controversy": "07_synthesis/CONTROVERSY_MAP.md",
         "boundary": "07_synthesis/BOUNDARY_CONDITIONS.md", "gap": "07_synthesis/GAP_MAP.md"}


def operation(function):
    """Reuse read-only source checks only within ONE single-writer operation, never across calls."""
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        if getattr(self, "_operation_depth", 0):
            return function(self, *args, **kwargs)
        self._operation_depth = 1
        restored = []
        try:
            for obj, names in ((self.rp, ("corpus", "context", "source")), (self.rp.dp, ("lookup",)), (self.rp.dp.store, ("load",))):
                for name in names:
                    original = getattr(obj, name)
                    cache = {}
                    def cached(*a, _original=original, _cache=cache, **kw):
                        key = digest([a, kw])
                        if key not in _cache:
                            _cache[key] = _original(*a, **kw)
                        return _cache[key]
                    restored.append((obj, name, original))
                    setattr(obj, name, cached)
            return function(self, *args, **kwargs)
        finally:
            for obj, name, original in restored:
                setattr(obj, name, original)
            self._operation_depth = 0
    return wrapped


def initialize_lab(root, source):
    """Copy an existing reading lab into a new isolated, non-approvable synthesis lab."""
    root, source = Path(root).resolve(), Path(source).resolve()
    require(not root.exists() and root != source, "NEW_ISOLATED_LAB_REQUIRED")
    require(not any((p / ".review/state.json").exists() or (p / "00_protocol/PROTOCOL.json").exists()
                    for p in root.parents), "LAB_MUST_BE_ISOLATED")
    rp = ReadingPipeline(source)
    require(rp.context().get("mode") == "isolated_scientific_reading", "READING_LAB_SOURCE_REQUIRED")
    validation = rp.validate()
    require(validation["valid"], "SOURCE_READING_INTEGRITY_FAILED:" + ";".join(validation["errors"]))
    require(bool(rp.latest("evidence")), "SOURCE_EVIDENCE_REQUIRED")
    require(not any(p.is_symlink() for p in source.rglob("*")), "SOURCE_SYMLINK_NOT_SUPPORTED")
    inventory = {str(p.relative_to(source)): checksum(p) for p in source.rglob("*") if p.is_file()}
    for name in ("03_library", "05_reading_notes", "06_evidence"):
        if (source / name).exists():
            shutil.copytree(source / name, root / name)
    # Preserve the upstream marker byte-for-byte: reading dependencies pin its hash.
    shutil.copy2(source / "READING_LAB.json", root / "READING_LAB.json")
    marker = {"mode": "isolated_provisional_synthesis", "project_id": "synthesis-lab-" + uuid.uuid4().hex,
              "source_name": source.name, "source_checksums": inventory,
              "notice": "Frozen upstream copy; no inherited official phase approvals; all judgments provisional."}
    write_json_atomic(root / "SYNTHESIS_LAB.json", marker)
    state = new_state(marker["project_id"], rp.context()["research_question"], "isolated-synthesis-pilot")
    state["reading_data"] = copy.deepcopy(rp.data)
    persist_state(root, state, "synthesis_lab_initialized")
    return marker


class SynthesisPipeline:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.state = load_state(self.root)
        self.data = self.state.setdefault("synthesis_data", {"contract_version": VERSION, "corpora": [],
                         "records": [], "semantics": [], "reviews": [], "exports": {}})
        self.rp = ReadingPipeline(self.root)

    @property
    def lab(self):
        return (self.root / "SYNTHESIS_LAB.json").exists()

    def integrity(self, projections=True):
        saved = load_state(self.root)
        last = json.loads((self.root / ".review/events.jsonl").read_text().splitlines()[-1])
        require(last["state_sha256"] == state_checksum(last["state"]) == state_checksum(saved), "SYNTHESIS_RECOVERY_REQUIRED")
        require(saved["seq"] == self.state["seq"], "RELOAD_SYNTHESIS_PIPELINE")
        if projections:
            for relative, sha in self.data["exports"].items():
                p = safe_path(self.root, relative)
                require(p.is_file() and checksum(p) == sha, "SYNTHESIS_EXPORT_CHANGED: preserve edits before recovery")
        self.rp.integrity()
        if self.lab:
            require(read(self.root / "SYNTHESIS_LAB.json").get("mode") == "isolated_provisional_synthesis", "INVALID_SYNTHESIS_LAB")
            require(self.rp.context().get("mode") == "isolated_scientific_reading", "LAB_CANNOT_BYPASS_REVIEW")

    def upstream(self):
        from ..independent_evaluation import gate
        independent = gate(self.root)
        if not independent['allowed']:
            return independent['blockers']
        if self.lab:
            result = self.rp.validate()
            return list(result["errors"])
        result = self.rp.completion(8)
        errors = list(result["blockers"])
        if self.state["phases"]["8"]["status"] != "completed":
            errors.append("PHASE8_NOT_COMPLETED")
        from ..validation import validate_protocol
        errors.extend(i.message for i in validate_protocol(self.root, require_approved=True))
        return errors

    def authorize(self, phase):
        self.integrity()
        require(not self.upstream(), "SYNTHESIS_UPSTREAM_BLOCKED:" + ";".join(self.upstream()))
        if not self.lab:
            require(self.state["phases"][str(phase)]["status"] == "in_progress", "SYNTHESIS_PHASE_NOT_ACTIVE")
            for previous in range(9, phase):
                require(self.state["phases"][str(previous)]["status"] == "completed"
                        and self.completion(previous)["allowed"], "SYNTHESIS_PREVIOUS_PHASE_NOT_CURRENT")

    def latest(self, kind=None):
        rows = {}
        for v in self.data["records"]:
            rows[v["record_id"]] = v
        return {k: v for k, v in rows.items() if kind is None or v["kind"] == kind}

    def corpus(self):
        require(bool(self.data["corpora"]), "SYNTHESIS_CORPUS_REQUIRED")
        return self.data["corpora"][-1]

    def evidence_version(self):
        return digest(self.rp.latest("evidence"))

    def search_version(self):
        # Content provenance, not developer-local paths; any changed coverage requires re-review.
        return {str(p.relative_to(self.root)): checksum(p) for folder in ("01_search", "02_discovery", "04_screening")
                for p in (self.root / folder).rglob("*") if p.is_file()}

    @operation
    def create_corpus(self, config):
        self.authorize(9)
        evidence = self.rp.latest("evidence")
        decisions = config.get("evidence_decisions", {})
        require(bool(evidence) and set(decisions) == set(evidence), "CORPUS_MUST_ACCOUNT_FOR_EVERY_EVIDENCE_ITEM")
        included = []
        for eid, d in decisions.items():
            require(d.get("disposition") in {"include", "exclude", "defer"} and nonempty(d.get("reason")), "CORPUS_DISPOSITION_REASON_REQUIRED")
            if d["disposition"] == "include":
                require(not self.rp.stale(evidence[eid], "evidence"), "STALE_EVIDENCE_NOT_ELIGIBLE")
                included.append(eid)
        require(bool(included), "NONEMPTY_SYNTHESIS_CORPUS_REQUIRED")
        for key in ("coverage_limitations", "search_coverage", "selection_rationale"):
            require(nonempty(config.get(key)), "CORPUS_FIELD_REQUIRED:" + key)
        protocol = self.rp.context()
        item = {"contract_version": VERSION, "corpus_id": "SC-" + uuid.uuid4().hex[:20],
                "revision_id": uuid.uuid4().hex, "version": len(self.data["corpora"]) + 1,
                "project_id": self.state["project_id"], "synthesis_run_id": "SR-" + uuid.uuid4().hex[:20],
                "protocol_version": protocol.get("protocol_version", protocol.get("version", "unversioned")),
                "protocol_hash": digest(protocol), "evidence_matrix_version": self.evidence_version(),
                "eligible_paper_ids": sorted(self.rp.corpus()), "included_evidence_ids": sorted(included),
                "excluded_or_deferred_evidence_ids": sorted(set(evidence) - set(included)),
                "evidence_decisions": copy.deepcopy(decisions), "research_question": protocol["research_question"],
                "subquestions": protocol.get("subquestions", []), "research_types": protocol["research_types"],
                "source_verification_levels": {eid: {"verification_status": v["verification_status"], "review_status": v["review_status"],
                    "extraction_status": v["extraction_status"], "stale": bool(self.rp.stale(v, "evidence"))} for eid, v in evidence.items()},
                "coverage_limitations": config["coverage_limitations"], "search_coverage": config["search_coverage"],
                "selection_rationale": config["selection_rationale"], "search_provenance": self.search_version(),
                "approval_status": "provisional" if self.lab else "pending", "created_at": utc_now()}
        item["corpus_checksum"] = digest(item)
        self.data["corpora"].append(item)
        self.save("synthesis_corpus_created")
        return item

    def corpus_errors(self):
        c = self.corpus()
        errors = []
        if c["protocol_hash"] != digest(self.rp.context()):
            errors.append("CORPUS_PROTOCOL_CHANGED")
        if c["evidence_matrix_version"] != self.evidence_version():
            errors.append("CORPUS_EVIDENCE_MATRIX_CHANGED")
        if c["search_provenance"] != self.search_version():
            errors.append("CORPUS_SEARCH_COVERAGE_CHANGED")
        for eid in c["included_evidence_ids"]:
            ev = self.rp.latest("evidence", eid)
            if not ev or self.rp.stale(ev, "evidence"):
                errors.append("CORPUS_SOURCE_STALE:" + eid)
        return errors

    def review_for(self, record):
        key = record.get("record_id", record.get("corpus_id"))
        return next((v for v in reversed(self.data["reviews"]) if v["record_id"] == key and v["revision_id"] == record["revision_id"]), None)

    def semantics_for(self, record):
        return next((v for v in reversed(self.data["semantics"]) if v["record_id"] == record["record_id"] and v["revision_id"] == record["revision_id"]), None)

    def binding(self, record):
        return digest({"record": record, "review": self.review_for(record), "semantics": self.semantics_for(record)})

    def retired(self, record):
        """Explicit human rejection retires a candidate, never erases it or hides unresolved deferral."""
        review = self.review_for(record)
        if review and review["action"] == "reject":
            return True
        if record.get("kind") == "link":
            claim = self.latest("claim").get(record["claim_id"])
            return bool(claim and self.retired(claim))
        return False

    def dependencies(self, kind, value):
        c = self.corpus()
        items = self.rp.latest("evidence")
        require(set(value["evidence_ids"]) <= set(c["included_evidence_ids"]), "EVIDENCE_NOT_IN_SYNTHESIS_CORPUS")
        refs = set(value["record_refs"])
        if kind == "link":
            refs.add(value["claim_id"])
        current = self.latest()
        for rid in refs:
            require(rid in current, "UNKNOWN_SYNTHESIS_REFERENCE:" + rid)
            other = current[rid]
            require(kind == "assessment" or not self.retired(other), "REJECTED_REFERENCE_REQUIRES_REVISION:" + rid)
            allowed = (kind == "assessment" and other["kind"] == value["map_kind"]) or (kind == "link" and other["kind"] == "claim")
            require(allowed or self.phase(other) < self.phase({**value, "kind": kind}), "CYCLIC_OR_FORWARD_REFERENCE")
            require(not self.stale(other), "STALE_SYNTHESIS_REFERENCE:" + rid)
        if kind == "gap":
            require(any(current[r]["kind"] == "claim" for r in refs), "GAP_CLAIM_REFERENCES_REQUIRED")
            # Pin all link judgments for each referenced claim, including counterevidence.
            refs.update(v["record_id"] for v in self.latest("link").values() if v["claim_id"] in refs)
        return {"corpus_revision": c["revision_id"], "protocol": digest(self.rp.context()),
                "evidence": {eid: digest(items[eid]) for eid in value["evidence_ids"]},
                "records": {rid: self.binding(current[rid]) for rid in sorted(refs)},
                "search": digest(self.search_version()) if kind == "gap" else None}

    def phase(self, record):
        return PHASE[record["map_kind"]] if record["kind"] == "assessment" else PHASE[record["kind"]]

    def stale(self, value):
        errors = []
        try:
            require(value["dependencies"] == self.dependencies(value["kind"], value), "SYNTHESIS_DEPENDENCY_CHANGED")
            for eid in value["evidence_ids"]:
                require(not self.rp.stale(self.rp.latest("evidence", eid), "evidence"), "UPSTREAM_EVIDENCE_STALE:" + eid)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append(str(exc))
        return errors

    @operation
    def submit(self, kind, config):
        validate_record(kind, config)
        self.authorize(self.phase({**config, "kind": kind}))
        require(not self.corpus_errors(), "SYNTHESIS_CORPUS_STALE")
        require(config["research_question"] == self.corpus()["research_question"], "RESEARCH_QUESTION_MISMATCH")
        require(set(config["evidence_ids"]) <= set(self.corpus()["included_evidence_ids"]), "EVIDENCE_NOT_IN_SYNTHESIS_CORPUS")
        current = self.latest()
        old = current.get(config.get("record_id"))
        if config.get("record_id"):
            require(old and old["kind"] == kind and config.get("supersedes_revision") == old["revision_id"], "CURRENT_REVISION_REQUIRED")
        if kind == "assessment":
            require(set(config["record_refs"]) == set(self.latest(config["map_kind"])), "ASSESSMENT_MUST_ACCOUNT_FOR_ENTIRE_MAP")
            require(bool(config["record_refs"]) == (config["disposition"] == "populated"), "ASSESSMENT_DISPOSITION_MISMATCH")
            require(set(config["evidence_ids"]) == set(self.corpus()["included_evidence_ids"]), "ASSESSMENT_MUST_COVER_CORPUS")
            existing = [v for v in self.latest("assessment").values() if v["map_kind"] == config["map_kind"]]
            require(not existing or (old and existing[0]["record_id"] == old["record_id"]), "REVISE_EXISTING_MAP_ASSESSMENT")
        if kind == "claim":
            require(set(config["evidence_decisions"]) == set(self.corpus()["included_evidence_ids"]), "CLAIM_MUST_ACCOUNT_FOR_COUNTEREVIDENCE")
            relevant = {eid for eid, d in config["evidence_decisions"].items() if d["relation"] != "not_relevant"}
            require(relevant == set(config["evidence_ids"]), "CLAIM_EVIDENCE_DISPOSITIONS_MISMATCH")
        if kind == "link":
            claim = current.get(config["claim_id"])
            require(claim and claim["kind"] == "claim", "UNKNOWN_CLAIM_ID")
            require(claim["evidence_decisions"].get(config["evidence_id"], {}).get("relation") == config["relation"], "LINK_DISPOSITION_MISMATCH")
            require(not any(v["claim_id"] == config["claim_id"] and v["evidence_id"] == config["evidence_id"] and v != old
                            for v in self.latest("link").values()), "REVISE_EXISTING_CLAIM_EVIDENCE_LINK")
        value = {k: copy.deepcopy(v) for k, v in config.items() if k not in {
            "record_id", "revision_id", "version", "dependencies", "review_status", "semantic_review_status", "approved_by", "approved_at",
            "contributing_paper_ids", "source_basis", "verification_status", "source_anchor_ids", "supersedes_revision", "created_at", "kind"}}
        rid = old["record_id"] if old else kind.upper() + "-" + uuid.uuid4().hex[:20]
        value.update(record_id=rid, kind=kind, revision_id=uuid.uuid4().hex, contract_version=VERSION,
                     version=old["version"] + 1 if old else 1, supersedes_revision=old["revision_id"] if old else None,
                     created_at=utc_now(), review_status="pending", semantic_review_status="not_assessed")
        value[kind + "_id"] = rid
        value["contributing_paper_ids"] = sorted({self.rp.latest("evidence", e)["paper_id"] for e in value["evidence_ids"]})
        value["research_types"] = sorted({t for e in value["evidence_ids"] for t in self.rp.latest("evidence", e)["research_types"]})
        if kind == "link":
            ev = self.rp.latest("evidence", value["evidence_id"])
            value.update(source_basis=ev["source_basis"], verification_status=ev["verification_status"], source_anchor_ids=ev["source_anchor_ids"],
                         reviewer=value["generator"], timestamp=value["created_at"])
        value["dependencies"] = self.dependencies(kind, value)
        self.data["records"].append(value)
        self.save("synthesis_record_submitted")
        return self.inspect(rid)

    def wording_checks(self, value):
        """Conservative structured guards, NOT an entailment/accuracy classifier."""
        issues = []
        evidence = [self.rp.latest("evidence", e) for e in value["evidence_ids"]]
        kind = value["kind"]
        if kind == "claim":
            supports = [e for e in evidence if value["evidence_decisions"][e["evidence_id"]]["relation"] == "supports"]
            if not supports:
                issues.append("NO_SUPPORTING_EVIDENCE")
            if value["claim_type"] == "causal" and (not supports or any(e["inference_class"] != "causal" for e in supports)):
                issues.append("CAUSAL_UPGRADE_NOT_SUPPORTED")
            if value["generalization"] != "source_bounded":
                issues.append("GENERALIZATION_BEYOND_SOURCES_REQUIRES_NEW_EVIDENCE")
            if value.get("claims_consensus") and len({e["paper_id"] for e in supports}) < 2:
                issues.append("MULTIPLE_ITEMS_NOT_INDEPENDENT_STUDIES")
            if value.get("claims_consensus") and any(d["relation"] in {"contradicts", "uncertain"} for d in value["evidence_decisions"].values()):
                issues.append("CONSENSUS_WITH_UNRESOLVED_DISAGREEMENT")
            if any(e["extraction_status"] != "supported" for e in supports):
                issues.append("UNCERTAIN_EVIDENCE_CANNOT_BE_VERIFIED_SUPPORT")
        if kind == "link":
            ev = evidence[0]
            if ev["citation_basis"] == "secondary_report" and value["directness"] == "direct_source":
                issues.append("SECONDARY_REPORT_IS_NOT_PRIMARY_VERIFICATION")
            if value["relation"] == "supports" and ev["extraction_status"] != "supported":
                issues.append("UNCERTAIN_EVIDENCE_CANNOT_BE_VERIFIED_SUPPORT")
        if kind == "boundary" and value["basis_level"] == "explicitly_tested" and not nonempty(value.get("within_source_test_basis")):
            issues.append("CROSS_STUDY_DIFFERENCE_IS_NOT_TESTED_MODERATION")
        if kind == "theory" and value["mechanism_status"] == "empirically_tested" and not nonempty(value.get("empirical_test_basis")):
            issues.append("PROPOSED_MECHANISM_IS_NOT_EMPIRICALLY_TESTED")
        if kind == "gap" and value.get("novelty_claim"):
            issues.append("NOVELTY_NOT_ESTABLISHED")
        return issues

    @operation
    def assess(self, rid, config):
        value = self.latest().get(rid)
        require(value is not None, "UNKNOWN_SYNTHESIS_ID")
        self.authorize(self.phase(value))
        require(not self.stale(value), "STALE_RECORD_CANNOT_BE_ASSESSED")
        validate_semantics(config)
        require(set(config["evidence_checks"]) == set(value["evidence_ids"])
                and all(nonempty(x) for x in config["evidence_checks"].values()), "ALL_REFERENCED_EVIDENCE_MUST_BE_SEMANTICALLY_ASSESSED")
        if config["outcome"] == "supported":
            require(not self.wording_checks(value), "STRUCTURED_OVERCLAIM_BLOCKED:" + ";".join(self.wording_checks(value)))
        result = {k: copy.deepcopy(config[k]) for k in ("outcome", "reviewer", "rationale", "checks", "evidence_checks")}
        result.update(record_id=rid, revision_id=value["revision_id"], assessment_id="SA-" + uuid.uuid4().hex[:20],
                      timestamp=utc_now(), authority="declared_semantic_assessment_not_human_approval", identity_authenticated=False)
        self.data["semantics"].append(result)
        self.save("synthesis_semantic_assessment")
        return result

    @operation
    def review(self, rid, action, by, rationale, changes=None):
        require(action in ACTIONS and nonempty(by) and nonempty(rationale), "NAMED_REVIEW_REASON_REQUIRED")
        require(not self.lab, "PROVISIONAL_LAB_CANNOT_RECORD_HUMAN_APPROVAL_OR_REVIEW")
        c = self.corpus()
        value = c if rid == c["corpus_id"] else self.latest().get(rid)
        require(value is not None, "UNKNOWN_SYNTHESIS_ID")
        self.authorize(9 if value is c else self.phase(value))
        if action == "approve":
            require(not self.corpus_errors(), "CORPUS_NOT_CURRENT")
            if value is not c:
                semantic = self.semantics_for(value)
                require(not self.stale(value) and not self.wording_checks(value), "RECORD_NOT_CURRENT_OR_OVERCLAIM")
                require(semantic and semantic["outcome"] == "supported", "SEMANTIC_REVIEW_REQUIRED")
        if action == "revise":
            require(value is not c and isinstance(changes, dict), "REVISE_RECORD_WITH_EXPLICIT_CHANGES")
            require(not set(changes) & {"record_id", "revision_id", "kind", "dependencies", "review_status"}, "PROTECTED_RECORD_FIELDS")
        record = {"review_id": "HR-" + uuid.uuid4().hex[:20], "record_id": rid, "revision_id": value["revision_id"],
                  "action": action, "by": by, "timestamp": utc_now(), "rationale": rationale, "identity_authenticated": False,
                  "semantic_assessment_id": (self.semantics_for(value) or {}).get("assessment_id") if value is not c else None}
        self.data["reviews"].append(record)
        self.save("synthesis_human_declared_review")
        if action == "revise":
            return self.submit(value["kind"], {**value, **changes, "supersedes_revision": value["revision_id"]})
        return record

    def approved(self, value):
        review = self.review_for(value)
        if not review or review["action"] != "approve":
            return False
        if "kind" in value:
            semantic = self.semantics_for(value)
            return bool(semantic and semantic["outcome"] == "supported" and review["semantic_assessment_id"] == semantic["assessment_id"])
        return True

    @operation
    def inspect(self, rid):
        value = self.latest().get(rid)
        require(value is not None, "UNKNOWN_SYNTHESIS_ID")
        traces = []
        for eid in value["evidence_ids"]:
            trace = self.rp.inspect("evidence", eid)
            ev = trace["record"]
            trace["reading_note"] = self.rp.inspect("notes", ev["reading_note_id"])
            trace["document_version"] = self.rp.dp.store.load()["documents"].get(ev["document_id"])
            trace["paper_identity"] = self.rp.registry.data["records"].get(ev["paper_id"])
            traces.append(trace)
        return {"record": value, "history": [v for v in self.data["records"] if v["record_id"] == rid],
                "semantic_assessment": self.semantics_for(value), "reviews": [v for v in self.data["reviews"] if v["record_id"] == rid],
                "stale_reasons": self.stale(value), "wording_flags": self.wording_checks(value),
                "effective_status": "retired" if self.retired(value) else "stale" if self.stale(value) else "human_approved" if self.approved(value) else "provisional",
                "trace": traces}

    @operation
    def validate(self):
        errors = []
        try:
            self.integrity()
            errors.extend(self.upstream())
            errors.extend(self.corpus_errors())
            for v in self.latest().values():
                validate_record(v["kind"], v)
                if not self.retired(v):
                    errors.extend(v["record_id"] + ":" + e for e in self.stale(v))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append(str(exc))
        return {"valid": not errors, "errors": errors, "record_count": len(self.latest()), "semantic_accuracy_validated": False,
                "independent_human_validation": False, "notice": "Valid means structure/provenance, not scientific entailment or approval."}

    @operation
    def completion(self, phase=11):
        require(phase in {9, 10, 11, 12}, "INVALID_SYNTHESIS_PHASE")
        # Later draft errors must not prevent correcting earlier phases.
        errors = []
        try:
            self.integrity()
            errors.extend(self.upstream())
            errors.extend(self.corpus_errors())
            if self.lab:
                errors.append("PROVISIONAL_LAB_CANNOT_PASS_OFFICIAL_GATE")
            if not self.approved(self.corpus()):
                errors.append("CORPUS_HUMAN_REVIEW_REQUIRED")
            for map_kind in MAPS:
                if PHASE[map_kind] > phase:
                    continue
                assessments = [v for v in self.latest("assessment").values() if v["map_kind"] == map_kind]
                if not assessments:
                    errors.append("MAP_ASSESSMENT_REQUIRED:" + map_kind)
                for a in assessments:
                    if set(a["record_refs"]) != set(self.latest(map_kind)) or a["disposition"] == "deferred":
                        errors.append("MAP_COVERAGE_INCOMPLETE:" + map_kind)
                if map_kind in {"theme", "method", "claim"} and not any(not self.retired(v) for v in self.latest(map_kind).values()):
                    errors.append("NONEMPTY_MAP_REQUIRED:" + map_kind)
            for v in self.latest().values():
                if self.phase(v) > phase:
                    continue
                if self.retired(v):
                    continue
                validate_record(v["kind"], v)
                errors.extend(v["record_id"] + ":" + e for e in self.stale(v) + self.wording_checks(v))
                if not self.approved(v):
                    errors.append("SEMANTIC_AND_HUMAN_REVIEW_REQUIRED:" + v["record_id"])
                if v["kind"] == "claim":
                    links = [link for link in self.latest("link").values() if link["claim_id"] == v["record_id"]]
                    expected = {(eid, d["relation"]) for eid, d in v["evidence_decisions"].items() if d["relation"] != "not_relevant"}
                    if {(l["evidence_id"], l["relation"]) for l in links} != expected:
                        errors.append("NORMALIZED_LINK_COVERAGE_REQUIRED:" + v["record_id"])
            if phase >= 11:
                covered = set().union(*(set(v["record_refs"]) for v in self.latest("claim").values() if not self.retired(v)))
                required = {v["record_id"] for v in self.latest().values() if v["kind"] in {"theme", "theory", "method", "controversy", "boundary"} and not self.retired(v)}
                if not required <= covered:
                    errors.append("SYNTHESIS_PROPOSITIONS_NOT_MAPPED_TO_CLAIMS")
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append(str(exc))
        return {"allowed": not errors, "phase": phase, "blockers": errors, "automatic_approval": False}

    def save(self, event):
        self.export()
        persist_state(self.root, self.state, event)
        self.rp = ReadingPipeline(self.root)

    def export(self):
        outputs = {}
        for kind, path in PATHS.items():
            records = list(self.latest(kind).values())
            assessments = [v for v in self.latest("assessment").values() if v["map_kind"] == kind]
            lines = ["# " + kind.title() + " map", "", "Projections only. Provisional until current semantic AND named human reviews pass.", ""]
            for v in records + assessments:
                lines += ["## " + v["record_id"], "", "```json", json.dumps({**v, "current_review": self.review_for(v),
                          "current_semantics": self.semantics_for(v)}, indent=2, ensure_ascii=False), "```", ""]
            outputs[path] = "\n".join(lines).encode()
        for kind, path in (("claim", "08_argument/CLAIM_MAP.csv"), ("link", "08_argument/CLAIM_EVIDENCE_LINKS.csv")):
            rows = []
            for v in self.latest(kind).values():
                row = {**v, "current_review": self.review_for(v), "current_semantics": self.semantics_for(v)}
                if kind == "claim":
                    decisions = v["evidence_decisions"]
                    row.update(claim=v["proposition"], supporting_evidence=";".join(e for e, d in decisions.items() if d["relation"] == "supports"),
                               contradictory_evidence=";".join(e for e, d in decisions.items() if d["relation"] == "contradicts"),
                               evidence_type=v["claim_type"], evidence_strength=v["strength"], boundary_conditions=v["scope"],
                               confidence=v["uncertainty"], verdict="retired_rejected" if self.retired(v) else "human_declared_approved" if self.approved(v) else "provisional", extension_json={})
                rows.append(row)
            legacy = ["claim_id", "claim", "supporting_evidence", "contradictory_evidence", "evidence_type", "evidence_strength",
                      "boundary_conditions", "allowed_wording", "prohibited_overclaim", "confidence", "verdict", "example_data", "extension_json"]
            fields = list(dict.fromkeys((legacy if kind == "claim" else ["link_id", "claim_id", "evidence_id", "relation", "directness"]) + [k for r in rows for k in r]))
            stream = io.StringIO(newline="")
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, bool)) else v for k, v in row.items()})
            outputs[path] = stream.getvalue().encode()
        outputs["07_synthesis/SYNTHESIS_HISTORY.json"] = json.dumps({k: v for k, v in self.data.items() if k != "exports"}, indent=2, ensure_ascii=False).encode()
        for relative, content in outputs.items():
            path = safe_path(self.root, relative)
            if path.exists() and relative not in self.data["exports"]:
                atomic_blob(self.root / "07_synthesis/legacy" / (checksum(path) + path.suffix), path.read_bytes())
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".synthesis-", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        self.data["exports"] = {p: checksum(safe_path(self.root, p)) for p in outputs}

    def recover(self):
        recover_state(self.root)
        self.__init__(self.root)
        self.export()
        persist_state(self.root, self.state, "synthesis_projections_recovered")
        self.rp = ReadingPipeline(self.root)
        return self.validate()
