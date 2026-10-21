from __future__ import annotations

import copy
import csv
import io
import json
import shutil
import uuid
from collections import Counter
from pathlib import Path

from ..state import load_state, new_state, persist_state, recover_state, state_checksum, utc_now, write_json_atomic
from ..documents.pipeline import DocumentPipeline
from ..documents.parser import checksum, parser_version
from ..documents.store import digest, safe_path, atomic_blob
from ..scholarly.registry import PaperRegistry
from ..project import load_schema_catalog
from .contracts import VERSION, CONTENT_FIELDS, EXTRA_FIELDS, require, nonempty, validate_note, validate_item


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def lab_context(root):
    marker = read(root / "READING_LAB.json")
    require(marker.get("mode") == "isolated_scientific_reading", "INVALID_READING_LAB")
    require(not (root / "00_protocol/PROTOCOL.json").exists(), "LAB_CANNOT_BYPASS_REVIEW")
    require(not any((p / ".review/state.json").exists() or (p / "00_protocol/PROTOCOL.json").exists()
                    for p in root.parents), "LAB_MUST_BE_ISOLATED")
    return marker


def initialize_lab(root, source, question, document_ids):
    root, source = Path(root).resolve(), Path(source).resolve()
    require(not root.exists() and nonempty(question), "NEW_ISOLATED_LAB_REQUIRED")
    require(not any((p / ".review/state.json").exists() or (p / "00_protocol/PROTOCOL.json").exists()
                    for p in root.parents), "LAB_MUST_BE_ISOLATED")
    dp = DocumentPipeline(source)
    registry = PaperRegistry(source)
    corpus = {}
    for document_id in document_ids:
        doc, _ = dp._document_file(dp.store.load(), document_id)
        require(doc["paper_id"] in registry.data["records"], "CANONICAL_ID_REQUIRED")
        require(doc["paper_id"] not in corpus, "ONE_SELECTED_VERSION_PER_PAPER")
        corpus[doc["paper_id"]] = {"document_id": document_id, "screening_decision_reference": "TEST_ONLY_NOT_ELIGIBILITY_APPROVAL"}
    require(bool(corpus), "PILOT_DOCUMENTS_REQUIRED")
    src = source / "03_library"
    require(not src.is_symlink() and not any(p.is_symlink() for p in src.rglob("*")), "SOURCE_SYMLINK_NOT_SUPPORTED")
    shutil.copytree(src, root / "03_library")
    marker = {"mode": "isolated_scientific_reading", "project_id": "reading-lab-" + uuid.uuid4().hex,
              "research_question": question, "protocol_version": "pilot-unapproved", "schema_version": "2.0.0",
              "research_types": list(load_schema_catalog()["research_type_extensions"]), "corpus": corpus,
              "source_name": source.name, "source_checksums": {str(p.relative_to(source)): checksum(p) for p in src.rglob("*") if p.is_file()},
              "notice": "Provisional AI interpretation only; not an official eligible corpus; no inherited approvals."}
    write_json_atomic(root / "READING_LAB.json", marker)
    persist_state(root, new_state(marker["project_id"], question, "isolated-reading-pilot"), "reading_lab_initialized")
    return marker


class ReadingPipeline:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.state = load_state(self.root)
        self.data = self.state.setdefault("reading_data", {"contract_version": VERSION, "notes": [], "evidence": [], "closures": [], "exports": {}})
        self.dp = DocumentPipeline(self.root)
        self.registry = PaperRegistry(self.root)

    def context(self):
        return lab_context(self.root) if (self.root / "READING_LAB.json").exists() else read(self.root / "00_protocol/PROTOCOL.json")

    def corpus(self):
        if self.context().get("mode") == "isolated_scientific_reading":
            return self.context()["corpus"]
        from ..screening.pipeline import ScreeningPipeline
        sp = ScreeningPipeline(self.root)
        gate = sp.gate()
        require(gate["allowed"], "GATE1_BLOCKED: " + ";".join(gate["errors"] + gate["blockers"]))
        return {pid: {"document_id": sp.latest(pid)["document_id"], "screening_decision_reference": sp.latest(pid)["decision_id"]}
                for pid in gate["eligible_paper_ids"]}

    def integrity(self, projections=True):
        saved = load_state(self.root)
        events = (self.root / ".review/events.jsonl").read_text().splitlines()
        last = json.loads(next(x for x in reversed(events) if x.strip()))
        require(last["state_sha256"] == state_checksum(last["state"]) == state_checksum(saved), "READING_RECOVERY_REQUIRED")
        # Concurrent/stale pipeline instances must not overwrite newer events.
        require(saved["seq"] == self.state["seq"], "RELOAD_READING_PIPELINE")
        if projections:
            for path, sha in self.data["exports"].items():
                p = safe_path(self.root, path)
                require(p.is_file() and checksum(p) == sha, "READING_EXPORT_CHANGED: preserve edits before reading-recover")

    def authorize(self, phase):
        self.integrity()
        self.corpus()
        if self.context().get("mode") == "isolated_scientific_reading":
            return
        require(self.state["phases"][str(phase)]["status"] == "in_progress", "READING_PHASE_NOT_ACTIVE")
        if phase == 8:
            require(self.state["phases"]["7"]["status"] == "completed", "PHASE7_INCOMPLETE")
            require(self.completion(7)["allowed"], "PHASE7_NOT_CURRENT")

    def source(self, paper_id, document_id):
        corpus = self.corpus()
        require(paper_id in self.registry.data["records"], "UNKNOWN_PAPER_ID")
        require(paper_id in corpus and corpus[paper_id]["document_id"] == document_id, "DOCUMENT_NOT_IN_READING_CORPUS")
        doc, _ = self.dp._document_file(self.dp.store.load(), document_id)
        require(doc["paper_id"] == paper_id and doc["version_kind"] != "unknown", "WRONG_DOCUMENT_IDENTITY_OR_VERSION")
        require(bool(doc["parse_refs"]), "DOCUMENT_NOT_PARSED")
        ref = doc["parse_refs"][-1]
        require(ref["parser_version"] == parser_version(), "PARSER_VERSION_CHANGED")
        parsed = self.dp._read_parse(doc, ref)
        return doc, parsed, ref

    def reading_context(self, paper_id, document_id):
        self.authorize(7)
        doc, parsed, ref = self.source(paper_id, document_id)
        return {"paper": self.registry.data["records"][paper_id], "document": doc, "parse": ref,
                "pages": parsed["pages"], "processing_limitations": parsed["processing_limitations"],
                "notice": "Page access is not proof of scientific reading. Inspect layouts and submit explicit coverage.",
                "content_fields": list(CONTENT_FIELDS), "protocol": self.context()}

    def latest(self, kind, stable_id=None):
        key = {"notes": "reading_note_id", "evidence": "evidence_id", "closures": "paper_id"}[kind]
        result = {}
        for item in self.data[kind]:
            result[item[key]] = item
        return result.get(stable_id) if stable_id is not None else result

    def note_for(self, paper_id):
        return next((v for v in reversed(list(self.latest("notes").values())) if v["paper_id"] == paper_id), None)

    def anchors(self, ids, document_id, paper_id):
        resolved = []
        require(len(ids) == len(set(ids)), "DUPLICATE_ANCHOR_ID")
        for aid in ids:
            a = self.dp.lookup(aid)
            require(a["effective_status"] in {"machine_located", "human_confirmed"}, "UNRESOLVED_SOURCE_ANCHOR:" + aid)
            require(a["document_id"] == document_id and a["paper_id"] == paper_id, "ANCHOR_WRONG_DOCUMENT")
            resolved.append(a)
        return resolved

    def dependencies(self, value, anchor_ids):
        doc, _, ref = self.source(value["paper_id"], value["document_id"])
        require(value["document_sha256"] == doc["sha256"], "DOCUMENT_CHECKSUM_MISMATCH")
        anchors = self.anchors(anchor_ids, value["document_id"], value["paper_id"])
        return {"protocol_hash": digest(self.context()), "identity_hash": digest(self.registry.data["records"][value["paper_id"]]),
                "document_identity": {k: doc[k] for k in ("document_id", "paper_id", "sha256", "version_kind", "access_basis")},
                "parse": ref, "screening": self.corpus()[value["paper_id"]],
                "anchors": {a["anchor_id"]: digest({k: v for k, v in a.items() if k not in {"resolved_pdf", "resolved_pdf_page", "resolved_text", "effective_status"}}) for a in anchors}}

    def stale(self, value, kind):
        errors = []
        try:
            require(value["dependencies"] == self.dependencies(value, value["source_anchor_ids"]), "SOURCE_DEPENDENCY_CHANGED")
            if kind == "evidence":
                note = self.latest("notes", value["reading_note_id"])
                require(note and note["revision_id"] == value["reading_note_revision"], "READING_NOTE_CHANGED")
                require(not self.stale(note, "notes"), "READING_NOTE_STALE")
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append(str(exc))
        return errors

    def _extensions(self, value):
        from ..validation import _extension_fields, _matches_declared_type
        catalog = load_schema_catalog()
        types = set(value["research_types"])
        require(types <= set(self.context().get("research_types", catalog["research_type_extensions"])), "UNSELECTED_RESEARCH_TYPE")
        require(types <= set(catalog["research_type_extensions"]), "UNKNOWN_RESEARCH_TYPE")
        if self.context().get("mode") == "isolated_scientific_reading":
            definitions = [{"name": n, "type": "string", "required": False, "research_types": [t]}
                           for t, names in catalog["research_type_extensions"].items() for n in names]
        else:
            definitions = _extension_fields(self.root)
        fields = {f["name"]: f for f in definitions}
        require(set(value["extension_json"]) <= set(fields), "UNKNOWN_EXTENSION_FIELD")
        for name, field in fields.items():
            applies = not field.get("research_types") or bool(types.intersection(field["research_types"]))
            require(not (applies and field.get("required")) or name in value["extension_json"], "REQUIRED_EXTENSION_MISSING:" + name)
            if name in value["extension_json"]:
                require(applies and _matches_declared_type(value["extension_json"][name], field["type"]), "EXTENSION_TYPE_OR_APPLICABILITY:" + name)

    def prepare(self, kind, config):
        v = copy.deepcopy(config)
        doc, parsed, _ = self.source(v["paper_id"], v["document_id"])
        require(v["document_sha256"] == doc["sha256"], "DOCUMENT_CHECKSUM_MISMATCH")
        if kind == "notes":
            validate_note(v)
            require(v.get("document_version") == doc["version_kind"], "WRONG_DOCUMENT_VERSION")
            pages = v["source_coverage"]["pages_read"]
            visual = v["source_coverage"]["visual_pages"]
            require(all(type(p) is int and 1 <= p <= parsed["page_count"] for p in pages + visual), "INVALID_COVERAGE_PAGE")
            require(len(pages) == len(set(pages)) and set(visual) <= set(pages), "INVALID_COVERAGE")
            if v["reading_status"] == "completed":
                require(set(pages) == set(range(1, parsed["page_count"] + 1)), "INCOMPLETE_PAGE_COVERAGE")
            ids = sorted({a for item in v["content"].values() for a in item.get("source_anchor_ids", [])})
            for anchor in self.anchors(ids, v["document_id"], v["paper_id"]):
                require(anchor["pdf_page"] in pages, "ANCHOR_PAGE_NOT_READ")
            v["source_anchor_ids"] = ids
            v["reading_procedure_version"] = VERSION
            v["screening_decision_reference"] = self.corpus()[v["paper_id"]]["screening_decision_reference"]
        else:
            validate_item(v)
            self._extensions(v)
            note = self.latest("notes", v["reading_note_id"])
            require(note and note["paper_id"] == v["paper_id"] and note["document_id"] == v["document_id"], "READING_NOTE_BINDING_MISMATCH")
            require(not self.stale(note, "notes"), "READING_NOTE_STALE")
            require(set(v["source_anchor_ids"]) <= set(note["source_anchor_ids"]), "EVIDENCE_NOT_GROUNDED_IN_READING_NOTE")
            require(v["research_question"] == self.context()["research_question"], "RESEARCH_QUESTION_MISMATCH")
            v["reading_note_revision"] = note["revision_id"]
            anchors = self.anchors(v["source_anchor_ids"], v["document_id"], v["paper_id"])
            if v["source_scope"] != "body_text" and v["extraction_status"] == "supported":
                require(nonempty(v.get("representation_assessment")) and all(a["pdf_page"] in note["source_coverage"]["visual_pages"] for a in anchors), "VISUAL_REPRESENTATION_REVIEW_REQUIRED")
            estimates = v.get("reported_values", [])
            require(isinstance(estimates, list), "REPORTED_VALUES_LIST_REQUIRED")
            for estimate in estimates:
                a = next((a for a in anchors if a["anchor_id"] == estimate.get("anchor_id")), None)
                require(a and nonempty(estimate.get("literal")) and estimate["literal"] in a["resolved_text"], "UNSUPPORTED_REPORTED_VALUE")
                require(all(nonempty(estimate.get(k)) for k in ("units", "denominator", "uncertainty")), "ESTIMATE_CONTEXT_REQUIRED")
            if v["extension_json"].get("effect_size") not in (None, "not_reported", "not_applicable", "uncertain", "not_reliably_extractable"):
                require(bool(estimates), "EFFECT_SIZE_SOURCE_REQUIRED")
            v["evidence_locator"] = [{"anchor_id": a["anchor_id"], "pdf_page": a["pdf_page"], "printed_page": a["printed_page"], "section": a["section"]} for a in anchors]
        v["protocol_version"] = self.context()["protocol_version"]
        v["dependencies"] = self.dependencies(v, v["source_anchor_ids"])
        v["verification_status"] = "partially_verified" if v["source_anchor_ids"] else "not_auditable"
        v["structural_verification"] = "source_resolved" if v["source_anchor_ids"] else "unresolved"
        return v

    def submit(self, kind, config):
        require(kind in {"notes", "evidence"}, "INVALID_RECORD_KIND")
        self.authorize(7 if kind == "notes" else 8)
        request_hash = digest(config)
        previous_request = next((v for v in self.data[kind] if v.get("request_hash") == request_hash), None)
        if previous_request:
            key = "reading_note_id" if kind == "notes" else "evidence_id"
            superseded = self.latest(kind, previous_request[key])["revision_id"] != previous_request["revision_id"]
            return {**previous_request, "effective_status": "stale" if superseded or self.stale(previous_request, kind) else "current", "replayed": True}
        require(nonempty(config.get("generator")), "GENERATOR_REQUIRED")
        v = self.prepare(kind, config)
        key = "reading_note_id" if kind == "notes" else "evidence_id"
        old = self.latest(kind, config.get(key)) if config.get(key) else None
        if kind == "notes" and old is None:
            require(self.note_for(v["paper_id"]) is None, "REVISE_EXISTING_NOTE_ID")
        require(not config.get(key) or old is not None, "UNKNOWN_STABLE_ID")
        require(not old or config.get("supersedes_revision") == old["revision_id"], "LATEST_REVISION_REQUIRED")
        if old:
            require(v["paper_id"] == old["paper_id"], "STABLE_ID_CANNOT_CHANGE_PAPER")
        v.update({key: old[key] if old else ("RN-" if kind == "notes" else "EV-") + uuid.uuid4().hex[:20],
                  "contract_version": VERSION, "revision_id": "RV-" + uuid.uuid4().hex[:20],
                  "supersedes_revision": old["revision_id"] if old else None, "created_at": utc_now(),
                  "request_hash": request_hash, "review_status": "pending", "review": None,
                  "identity_authenticated": False, "semantic_verification": "provisional_ai_interpretation"})
        self.data[kind].append(v)
        self.save("reading_" + kind + "_proposed")
        return v

    def review(self, kind, stable_id, action, by, comment, changes=None):
        self.authorize(7 if kind == "notes" else 8)
        require(self.context().get("mode") != "isolated_scientific_reading", "PILOT_CANNOT_HUMAN_APPROVE")
        require(nonempty(by) and nonempty(comment), "DECLARED_REVIEWER_AND_COMMENT_REQUIRED")
        require(action in {"accept", "reject", "correct", "uncertain", "incomplete", "reread", "comment"}, "INVALID_REVIEW_ACTION")
        old = self.latest(kind, stable_id)
        require(old is not None, "UNKNOWN_READING_RECORD")
        if action in {"accept", "comment"}:
            require(not self.stale(old, kind), "STALE_RECORD_REQUIRES_REVISION")
        v = copy.deepcopy(old)
        if action == "correct":
            require(isinstance(changes, dict) and bool(changes), "CORRECTION_REQUIRED")
            protected = {"paper_id", "reading_note_id", "evidence_id", "review_status", "review", "revision_id", "created_at", "dependencies", "protocol_version", "verification_status"}
            require(not set(changes).intersection(protected), "PROTECTED_CORRECTION_FIELD")
            v.update(changes)
            v = self.prepare(kind, v)
        status = {"accept": "accepted", "reject": "rejected", "correct": "pending", "uncertain": "uncertain", "incomplete": "incomplete", "reread": "reread", "comment": old["review_status"]}[action]
        if action == "accept":
            require(bool(v["source_anchor_ids"]), "UNRESOLVED_RECORD_CANNOT_BE_ACCEPTED")
            if kind == "evidence":
                require(v["extraction_status"] == "supported", "UNSUPPORTED_EXTRACTION_CANNOT_BE_ACCEPTED")
        v.update(revision_id="RV-" + uuid.uuid4().hex[:20], supersedes_revision=old["revision_id"],
                 created_at=utc_now(), request_hash=None, review_status=status,
                 review={"action": action, "by": by, "comment": comment, "at": utc_now(), "identity_authenticated": False},
                 semantic_verification="human_declared_review" if status == "accepted" else "not_approved")
        self.data[kind].append(v)
        self.save("reading_human_declared_review")
        return v

    def inspect(self, kind, stable_id):
        v = self.latest(kind, stable_id)
        require(v is not None, "UNKNOWN_READING_RECORD")
        resolved, unresolved = [], []
        for aid in v["source_anchor_ids"]:
            try:
                resolved.append(self.dp.lookup(aid))
            except ValueError as exc:
                unresolved.append(str(exc))
        errors = self.stale(v, kind)
        return {"record": v, "effective_status": "stale" if errors else "current", "stale_reasons": errors,
                "anchors": resolved, "unresolved_links": unresolved, "history": [x for x in self.data[kind] if x.get("reading_note_id" if kind == "notes" else "evidence_id") == stable_id],
                "semantic_accuracy": "Not established by structural validation"}

    def close_extraction(self, paper_id, status, explanation, by=None):
        self.authorize(8)
        require(paper_id in self.corpus(), "PAPER_NOT_ELIGIBLE")
        require(status in {"complete", "no_relevant_findings", "incomplete", "failed"} and nonempty(explanation), "EXTRACTION_DISPOSITION_REQUIRED")
        require(not by or self.context().get("mode") != "isolated_scientific_reading", "PILOT_CANNOT_HUMAN_APPROVE")
        require(by is None or nonempty(by), "DECLARED_REVIEWER_REQUIRED")
        note = self.note_for(paper_id)
        require(note and not self.stale(note, "notes"), "CURRENT_READING_NOTE_REQUIRED")
        evidence = {k: v["revision_id"] for k, v in self.latest("evidence").items() if v["paper_id"] == paper_id}
        if status == "no_relevant_findings":
            require(not evidence, "ZERO_EVIDENCE_DISPOSITION_CONFLICT")
        v = {"paper_id": paper_id, "status": status, "explanation": explanation, "by": by,
             "note_revision": note["revision_id"], "evidence_revisions": evidence, "at": utc_now(),
             "review_status": "human_declared" if by else "pending", "identity_authenticated": False}
        self.data["closures"].append(v)
        self.save("extraction_coverage_disposition")
        return v

    def coverage(self):
        rows, errors = [], []
        try:
            corpus = self.corpus()
        except (ValueError, OSError, KeyError) as exc:
            corpus, errors = {}, [str(exc)]
        for pid, binding in corpus.items():
            note = self.note_for(pid)
            parser_status, parser_limitations = "unavailable", []
            try:
                doc, parsed, _ = self.source(pid, binding["document_id"])
                parser_status = doc["parsing_status"]
                parser_limitations = parsed["processing_limitations"]
            except (ValueError, OSError, KeyError) as exc:
                parser_limitations = [str(exc)]
            items = [v for v in self.latest("evidence").values() if v["paper_id"] == pid]
            closure = self.latest("closures", pid)
            note_stale = self.stale(note, "notes") if note else []
            current_revisions = {v["evidence_id"]: v["revision_id"] for v in items}
            closure_current = bool(closure and note and closure["note_revision"] == note["revision_id"] and closure["evidence_revisions"] == current_revisions)
            rows.append({"paper_id": pid, **binding, "reading_status": note["reading_status"] if note else "not_started",
                         "reading_review": note["review_status"] if note else "not_started", "reading_stale": note_stale,
                         "source_coverage": note["source_coverage"] if note else None,
                         "unresolved_material": note["unresolved_material"] if note else [],
                         "parser_status": parser_status, "parsing_limitations": parser_limitations,
                         "evidence_count": len(items), "valid_anchored_items": sum(bool(v["source_anchor_ids"]) and not self.stale(v, "evidence") for v in items),
                         "evidence_pending_review": sum(v["review_status"] != "accepted" for v in items),
                         "unsupported_ambiguous_items": sum(v["extraction_status"] != "supported" or not v["source_anchor_ids"] for v in items),
                         "stale_items": sum(bool(self.stale(v, "evidence")) for v in items),
                         "extraction_disposition": closure if closure_current else None})
        return {"mode": self.context().get("mode", "official"), "eligible_papers": len(corpus) if not self.context().get("mode") else 0,
                "pilot_selected_papers": len(corpus) if self.context().get("mode") else 0,
                "papers": rows, "reading_counts": dict(Counter(r["reading_status"] for r in rows)),
                "evidence_count": len(self.latest("evidence")), "reconciled": sum(r["evidence_count"] for r in rows) == len(self.latest("evidence")),
                "reading_awaiting_review": sum(r["reading_review"] not in {"accepted", "not_started"} for r in rows),
                "documents_with_unresolved_material": sum(bool(r["unresolved_material"]) for r in rows),
                "documents_with_parser_limitations": sum(bool(r["parsing_limitations"]) for r in rows),
                "errors": errors, "notice": "Zero rows do not demonstrate absence of relevant findings; closure requires documented inspection and human review."}

    def validate(self, include_evidence=True):
        errors = []
        try:
            self.integrity()
            self.corpus()
        except (ValueError, OSError, KeyError) as exc:
            errors.append(str(exc))
        for kind in (("notes", "evidence") if include_evidence else ("notes",)):
            for v in self.latest(kind).values():
                try:
                    (validate_note if kind == "notes" else validate_item)(v)
                    if kind == "evidence":
                        self._extensions(v)
                    errors.extend(v["revision_id"] + ":" + e for e in self.stale(v, kind))
                except (ValueError, KeyError, TypeError) as exc:
                    errors.append(str(exc))
        coverage = self.coverage()
        if not coverage["reconciled"]:
            errors.append("EVIDENCE_CORPUS_COUNT_MISMATCH")
        return {"valid": not errors, "errors": errors, "semantic_accuracy_validated": False, "coverage": coverage}

    def completion(self, phase=8):
        result = self.validate(include_evidence=phase == 8)
        blockers = list(result["errors"])
        if self.context().get("mode"):
            blockers.append("ISOLATED_PILOT_CANNOT_COMPLETE_PHASE_OR_PASS_GATE2")
        if not self.data["notes"]:
            blockers.append("STRUCTURED_READING_NOTES_REQUIRED")
        for row in result["coverage"]["papers"]:
            pid = row["paper_id"]
            note = self.note_for(pid)
            if not note or row["reading_status"] != "completed" or row["reading_review"] != "accepted" or row["reading_stale"]:
                blockers.append(pid + ":READING_INCOMPLETE_OR_AWAITING_REVIEW")
            if note and any(v["status"] == "present" and not v.get("source_anchor_ids") for v in note["content"].values()):
                blockers.append(pid + ":UNGROUNDED_NOTE_CONTENT")
            if phase == 8:
                closure = row["extraction_disposition"]
                if not closure or closure["review_status"] != "human_declared" or closure["status"] not in {"complete", "no_relevant_findings"}:
                    blockers.append(pid + ":EXTRACTION_COVERAGE_REVIEW_REQUIRED")
                if row["evidence_pending_review"] or row["unsupported_ambiguous_items"] or row["stale_items"]:
                    blockers.append(pid + ":EXTRACTIONS_REQUIRE_RESOLUTION_AND_REVIEW")
                if not row["evidence_count"] and (not closure or closure["status"] != "no_relevant_findings"):
                    blockers.append(pid + ":ZERO_EVIDENCE_NOT_EXPLAINED")
        if phase == 8 and str(self.context().get("schema_version", "1")).startswith("1"):
            blockers.append("LEGACY_MATRIX_PRESERVED_EXPLICIT_MIGRATION_REVIEW_REQUIRED")
        return {"allowed": not blockers, "status": "blocked" if blockers else "pass", "blockers": blockers,
                "coverage": result["coverage"], "automatic_approval": False}

    def save(self, event):
        self.export()
        persist_state(self.root, self.state, event)

    def export(self):
        outputs = {"05_reading_notes/READING_NOTES.json": self.data["notes"],
                   "06_evidence/EVIDENCE_ITEMS.json": self.data["evidence"],
                   "06_evidence/EXTRACTION_COVERAGE_HISTORY.json": self.data["closures"]}
        for relative, value in outputs.items():
            write_json_atomic(safe_path(self.root, relative), value)
        note_paths = []
        for note in self.latest("notes").values():
            relative = "05_reading_notes/" + note["reading_note_id"] + ".md"
            lines = ["# Paper reading note", "", f"Paper: {note['paper_id']} | Document: {note['document_id']}",
                     f"Revision: {note['revision_id']} | Review: {note['review_status']}",
                     "", "Source-located AI interpretation is not independently verified scientific evidence.",
                     "", "## Coverage", "", json.dumps(note["source_coverage"], ensure_ascii=False),
                     "", "Unresolved material: " + json.dumps(note["unresolved_material"], ensure_ascii=False)]
            for key, value in note["content"].items():
                lines += ["", "## " + key, "", value["status"] + ": " + value.get("text", value.get("reason", "")),
                          "", "Role: " + value.get("epistemic_role", "not_applicable"),
                          "Anchors: " + ", ".join(value.get("source_anchor_ids", []))]
            safe_path(self.root, relative).write_text("\n".join(lines) + "\n", encoding="utf-8")
            note_paths.append(relative)
        fields = load_schema_catalog()["universal_core"]["evidence"] + EXTRA_FIELDS
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in self.latest("evidence").values():
            writer.writerow({k: json.dumps(item[k], ensure_ascii=False) if isinstance(item.get(k), (list, dict, bool)) else item.get(k, "") for k in fields})
        relative = "06_evidence/EVIDENCE_MATRIX_V2.csv" if str(self.context().get("schema_version", "1")).startswith("1") else "06_evidence/EVIDENCE_MATRIX.csv"
        path = safe_path(self.root, relative)
        if path.exists() and relative not in self.data["exports"]:
            atomic_blob(self.root / "06_evidence/legacy" / (checksum(path) + ".csv"), path.read_bytes())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stream.getvalue(), encoding="utf-8")
        outputs[relative] = None
        self.data["exports"] = {relative: checksum(safe_path(self.root, relative)) for relative in [*outputs, *note_paths]}

    def recover(self):
        recover_state(self.root)
        self.__init__(self.root)
        self.export()
        persist_state(self.root, self.state, "reading_projections_recovered")
        return self.validate()
