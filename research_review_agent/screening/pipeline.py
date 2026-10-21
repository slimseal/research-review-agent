from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import uuid
from collections import Counter
from pathlib import Path

from ..state import canonical_json, load_state, new_state, persist_state, recover_state, utc_now, write_json_atomic, state_checksum
from ..scholarly.registry import PaperRegistry
from ..scholarly.normalization import normalize_title, _clean_abstract, _openalex_abstract
from ..documents.store import DocumentStore, safe_path, atomic_blob
from ..documents.parser import checksum, parser_version, run_parser
from .contracts import STAGES, DECISIONS, ROLES, FIELDS, validate_decision


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def initialize_lab(root, source, question):
    """Copy upstream artifacts, never their workflow approvals. No network operations."""
    root, source = Path(root).resolve(), Path(source).resolve()
    if root.exists() or not question.strip():
        raise ValueError("NEW_LAB_AND_RESEARCH_QUESTION_REQUIRED")
    if any((p / ".review/state.json").exists() or (p / "00_protocol/PROTOCOL.json").exists() for p in root.parents):
        raise ValueError("LAB_MUST_BE_ISOLATED")
    if not (source / "03_library/PAPER_IDENTITIES.json").is_file():
        raise ValueError("CANONICAL_REGISTRY_REQUIRED")
    root.mkdir(parents=True)
    hashes = {}
    for directory in ("01_search", "02_discovery", "03_library"):
        src = source / directory
        if src.exists():
            # Do not follow imported symlinks outside a source workspace.
            if any(p.is_symlink() for p in src.rglob("*")):
                raise ValueError("SOURCE_SYMLINK_NOT_SUPPORTED")
            shutil.copytree(src, root / directory)
            for p in (root / directory).rglob("*"):
                if p.is_file():
                    hashes[str(p.relative_to(root))] = checksum(p)
    marker = {"project_id": "screening-lab-" + uuid.uuid4().hex, "research_question": question,
              "protocol_version": "pilot-unapproved", "mode": "isolated_screening",
              "source_name": source.name, "source_checksums": hashes, "created_at": utc_now(),
              "notice": "Real metadata or explicitly fictional tests; no inherited human approvals or phase completion."}
    write_json_atomic(root / "SCREENING_LAB.json", marker)
    persist_state(root, new_state(marker["project_id"], question, "screening-infrastructure-lab"), "screening_lab_initialized")
    return marker


class ScreeningPipeline:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.state = load_state(self.root)
        self.registry = PaperRegistry(self.root)
        self.data = self.state.setdefault("screening_data", {"contract_version": "1.0.0", "criteria": [],
            "packets": {}, "decisions": [], "approvals": [], "exports": {}})

    def context(self):
        marker = self.root / "SCREENING_LAB.json"
        if marker.exists():
            if any((p / "00_protocol/PROTOCOL.json").exists() for p in (self.root, *self.root.parents)):
                raise ValueError("LAB_CANNOT_BYPASS_REVIEW")
            result = read(marker)
            if result.get("mode") != "isolated_screening":
                raise ValueError("INVALID_SCREENING_LAB")
            return result
        return read(self.root / "00_protocol/PROTOCOL.json")

    def upstream(self):
        from ..validation import validate_protocol, validate_phase
        if self.context().get("mode") == "isolated_screening":
            return ["ISOLATED_PILOT_NOT_OFFICIAL", "PHASE4_HUMAN_APPROVAL_NOT_INHERITED"]
        issues = validate_protocol(self.root, require_approved=True, require_substantive=True)
        # Never trust a manually set phase flag or absence of citation_data.
        for phase in (3, 4, 5):
            if self.state["phases"][str(phase)]["status"] != "completed":
                issues.append(type("Problem", (), {"message": f"PHASE_{phase}_INCOMPLETE"})())
            issues.extend(validate_phase(self.root, phase))
        return [i.message for i in issues]

    def authorize(self):
        self.check_journal()
        for relative, sha in self.data["exports"].items():
            path = safe_path(self.root, relative)
            if not path.exists() or checksum(path) != sha:
                raise ValueError("SCREENING_EXPORT_CHANGED: inspect edits, then screening-recover; no silent overwrite")
        if self.context().get("mode") == "isolated_screening":
            return
        issues = self.upstream()
        if issues:
            raise ValueError("SCREENING_UPSTREAM_BLOCKED: " + "; ".join(issues))
        if self.state["phases"]["6"]["status"] != "in_progress":
            raise ValueError("PHASE6_NOT_ACTIVE")

    def check_journal(self):
        from ..journal_tail import last_event
        last = last_event(self.root / ".review/events.jsonl")
        persisted = load_state(self.root)
        if last.get("state_sha256") != state_checksum(persisted) or last.get("state_sha256") != state_checksum(last["state"]):
            raise ValueError("SCREENING_STATE_JOURNAL_MISMATCH: recover before continuing")

    def save(self, event):
        state = load_state(self.root)
        state["screening_data"] = self.data
        self.state = persist_state(self.root, state, event)
        self.export()

    def current(self):
        if not self.data["criteria"]:
            raise ValueError("SCREENING_CRITERIA_REQUIRED")
        return self.data["criteria"][-1]

    def register(self, config, reason):
        self.authorize()
        if not reason.strip():
            raise ValueError("CHANGE_REASON_REQUIRED")
        rules = config.get("rules", [])
        seen = set()
        for r in rules:
            if not r.get("id") or r["id"] in seen or not r.get("text") or r.get("kind") not in {"include", "exclude"} or not r.get("stages") or set(r["stages"]) - set(STAGES):
                raise ValueError("INVALID_CRITERION")
            seen.add(r["id"])
            if r.get("paper_ids") and set(r["paper_ids"]) - set(self.registry.data["records"]):
                raise ValueError("UNKNOWN_CRITERION_PAPER")
        if not rules:
            raise ValueError("POPULATED_CRITERIA_REQUIRED")
        context = self.context()
        if context.get("mode") != "isolated_screening":
            # An operationalization must map every approved criterion, without rewriting Protocol.
            for kind in ("include", "exclude"):
                approved = context["screening"][kind]
                if any(r["text"] not in approved for r in rules if r["kind"] == kind) or set(approved) != {r["text"] for r in rules if r["kind"] == kind}:
                    raise ValueError("CRITERIA_MUST_TRACE_TO_APPROVED_PROTOCOL")
        ids = config.get("candidate_ids", list(self.registry.data["records"]))
        omitted = config.get("scope_exceptions", {})
        if not ids or len(ids) != len(set(ids)) or set(ids) - set(self.registry.data["records"]):
            raise ValueError("NONEMPTY_UNIQUE_CANONICAL_CANDIDATES_REQUIRED")
        if any(self.registry.data["records"][pid].get("verification_status") == "conflict" for pid in ids):
            raise ValueError("RESOLVE_IDENTITY_CONFLICT_OR_EXPLICITLY_BOUND_SCOPE")
        missing = set(self.registry.data["records"]) - set(ids)
        if set(omitted) != missing or any(not isinstance(v, str) or not v.strip() for v in omitted.values()):
            raise ValueError("BOUNDED_SCOPE_EXCEPTIONS_REQUIRED")
        roles = sorted(ROLES | set(config.get("role_extensions", {})))
        if any(not isinstance(v, str) or not v.strip() for v in config.get("role_extensions", {}).values()):
            raise ValueError("ROLE_EXTENSION_JUSTIFICATION_REQUIRED")
        versions = config.get("accepted_versions", ["version_of_record", "accepted_manuscript", "preprint"])
        if not versions or set(versions) - {"version_of_record", "accepted_manuscript", "preprint", "supplementary"}:
            raise ValueError("EXPLICIT_DOCUMENT_VERSION_POLICY_REQUIRED")
        value = {"version": len(self.data["criteria"]) + 1, "rules": rules, "roles": roles,
                 "role_extensions": config.get("role_extensions", {}), "accepted_versions": versions,
                 "candidate_ids": ids, "scope_exceptions": omitted, "protocol_version": context["protocol_version"],
                 "protocol_sha256": digest(context), "reason": reason, "created_at": utc_now(),
                 "registry_snapshot": {pid: digest(rec) for pid, rec in self.registry.data["records"].items()}}
        value["candidate_set_version"] = digest({"ids": ids, "exceptions": omitted, "registry": value["registry_snapshot"]})
        if self.data["criteria"]:
            old = self.current()
            if old["protocol_sha256"] != digest(context):
                raise ValueError("PROTOCOL_AMENDMENT_REQUIRES_UPSTREAM_REVIEW; old screening retained")
        self.data["criteria"].append(value)
        if len(self.data["criteria"]) == 1:
            for name in ("SCREENING_MASTER.csv", "EXCLUSION_LOG.csv"):
                path = self.root / "04_screening" / name
                if path.exists():
                    atomic_blob(self.root / "04_screening/legacy" / (checksum(path) + "-" + name), path.read_bytes())
        self.save("screening_criteria_registered")
        return value

    def approve_criteria(self, by, note):
        self.authorize()
        if self.context().get("mode") == "isolated_screening":
            raise ValueError("PILOT_CANNOT_APPROVE_RESEARCH_SCOPE")
        if not by.strip() or not note.strip():
            raise ValueError("NAMED_EXPLICIT_HUMAN_REVIEW_REQUIRED")
        self.data["approvals"].append({"criteria_sha256": digest(self.current()), "by": by, "note": note,
                                        "at": utc_now(), "identity_authenticated": False})
        self.save("screening_criteria_human_review")
        return self.data["approvals"][-1]

    def require_criteria_approval(self):
        if self.context().get("mode") != "isolated_screening" and not any(a["criteria_sha256"] == digest(self.current()) for a in self.data["approvals"]):
            raise ValueError("APPROVE_CRITERIA_AND_SCOPE_BEFORE_OFFICIAL_SCREENING")

    def rules_for(self, version, pid, stage):
        return {r["id"]: r for r in version["rules"] if stage in r["stages"] and (not r.get("paper_ids") or pid in r["paper_ids"])}

    def latest(self, pid, stage=None):
        values = [d for d in self.data["decisions"] if d["paper_id"] == pid and (stage is None or d["screening_stage"] == stage)]
        if stage is not None:
            return values[-1] if values else None
        # A later-stage record cannot conceal a newer reopening of an earlier stage.
        return max(values, key=lambda d: (STAGES.index(d["screening_stage"]), self.data["decisions"].index(d))) if values else None

    def abstract(self, pid):
        """Select a raw record bound to a canonical identity; preserve raw abstract and pointer."""
        record = self.registry.data["records"][pid]
        for pointer in record.get("provenance", []):
            relative = pointer.get("raw_response_path")
            if not relative:
                continue
            path = safe_path(self.root, relative)
            if not path.exists():
                continue
            obj = read(path)
            provider = pointer.get("provider")
            if provider == "crossref":
                body = obj.get("message", obj)
                records = body.get("items", [body]) if isinstance(body, dict) else []
            elif provider == "openalex":
                records = obj.get("results", [obj])
            else:
                continue
            for row in records:
                if not isinstance(row, dict):
                    continue
                rawdoi = str(row.get("DOI") or row.get("doi") or "").lower().removeprefix("https://doi.org/")
                title = row.get("title") or row.get("display_name")
                title = title[0] if isinstance(title, list) and title else title
                matches = rawdoi == record["doi"] if rawdoi and record.get("doi") else normalize_title(title) == normalize_title(record["title"])
                if not matches:
                    continue
                raw = row.get("abstract") if provider == "crossref" else row.get("abstract_inverted_index")
                text = _clean_abstract(raw) if provider == "crossref" else _openalex_abstract(raw)
                if text:
                    return {"text": text, "original": raw, "provider": provider,
                            "raw_response_path": relative, "raw_sha256": checksum(path), "provenance": pointer}
        return {"text": None, "original": None, "status": "missing_abstract"}

    def stage_context(self, pid, stage, document_id=None, pages=None):
        self.authorize()
        self.require_criteria_approval()
        current = self.current()
        if pid not in current["candidate_ids"] or stage not in STAGES:
            raise ValueError("UNKNOWN_CANDIDATE_OR_STAGE")
        if current["protocol_sha256"] != digest(self.context()):
            raise ValueError("PROTOCOL_CHANGED")
        previous = None
        if stage != "title":
            previous = self.latest(pid, STAGES[STAGES.index(stage) - 1])
            if not previous or previous["decision"] == "exclude" or self.stale(previous):
                raise ValueError("CURRENT_PREVIOUS_STAGE_REQUIRED")
        r = self.registry.data["records"][pid]
        packet = {"paper_id": pid, "stage": stage, "criteria_version": current["version"],
                  "candidate_set_version": current["candidate_set_version"], "registry_sha256": digest(r),
                  "previous_stage_id": previous["decision_id"] if previous else None,
                  "basic_metadata": {k: r.get(k) for k in ("title", "authors", "publication_year", "doi", "work_type", "version_type", "related_versions")},
                  "source_basis": stage, "document_id": None, "eligibility_status": "not_applicable"}
        packet["metadata_provenance"] = r.get("provenance", [])
        if stage == "abstract":
            packet["abstract"] = self.abstract(pid)
        if stage == "fulltext_eligibility":
            packet.update(source_basis="full_text_unavailable", eligibility_status="awaiting_authorized_import", pages=[])
            if not document_id:
                access = self.root / "03_library/ACQUISITION_REVIEW.json"
                disposition = read(access).get("papers", {}).get(pid, {}) if access.exists() else {}
                packet["acquisition_disposition"] = disposition
                if disposition.get("status") == "unavailable":
                    packet["eligibility_status"] = "fulltext_unavailable"
                attempts = [a for a in DocumentStore(self.root).load()["attempts"].values() if a["paper_id"] == pid]
                if attempts and attempts[-1].get("failure_code") in {"ACCESS_FORBIDDEN", "ACCESS_NOT_AUTHORIZED"}:
                    packet["eligibility_status"] = "fulltext_not_lawfully_accessible"
                    packet["acquisition_attempt_id"] = attempts[-1]["attempt_id"]
            if document_id:
                from ..documents.pipeline import DocumentPipeline
                pipeline = DocumentPipeline(self.root)
                document, path = pipeline._document_file(pipeline.store.load(), document_id)
                packet.update(document_id=document_id, document_sha256=document["sha256"], version_kind=document["version_kind"],
                              access_basis=document["access_basis"], license_status=document["license_status"])
                if document["paper_id"] != pid or document["version_kind"] not in current["accepted_versions"]:
                    packet["eligibility_status"] = "wrong_document_version"
                elif document["access_basis"] not in {"publisher_open_access", "researcher_asserted_authorized"}:
                    packet["eligibility_status"] = "fulltext_not_lawfully_accessible"
                else:
                    if not pages or len(set(pages)) > 5 or any(not isinstance(p, int) or p < 1 or p > document["pdf_page_count"] for p in pages):
                        raise ValueError("TARGETED_PAGES_REQUIRED: 1 to 5 explicit PDF pages per eligibility context")
                    # Mechanical parsing is not scientific reading. Only selected pages leave this operation.
                    parsed = run_parser(path, extract=True)
                    packet["parser_version"] = parser_version()
                    packet["pages"] = [p for p in parsed["pages"] if p["pdf_page"] in pages]
                    packet["source_basis"] = "targeted_full_text"
                    packet["eligibility_status"] = "available_not_yet_assessed" if len(packet["pages"]) == len(set(pages)) and all(p.get("text", "").strip() for p in packet["pages"]) else "text_extraction_insufficient"
        packet_id = "SP-" + digest(packet)
        packet["packet_id"] = packet_id
        relative = f"04_screening/packets/{packet_id}.json"
        atomic_blob(safe_path(self.root, relative), (canonical_json(packet) + "\n").encode())
        self.data["packets"][packet_id] = {"path": relative, "sha256": checksum(self.root / relative)}
        self.save("screening_context_created")
        return packet

    def packet(self, packet_id):
        ref = self.data["packets"][packet_id]
        path = safe_path(self.root, ref["path"])
        if checksum(path) != ref["sha256"]:
            raise ValueError("SCREENING_PACKET_CHECKSUM_MISMATCH")
        value = read(path)
        if value["packet_id"] != packet_id:
            raise ValueError("PACKET_BINDING_MISMATCH")
        return value

    def propose(self, proposal):
        self.authorize()
        self.require_criteria_approval()
        current = self.current()
        packet = self.packet(proposal["packet_id"])
        if packet["criteria_version"] != current["version"] or packet["candidate_set_version"] != current["candidate_set_version"]:
            raise ValueError("NEW_CONTEXT_REQUIRED_FOR_NEW_CRITERIA")
        pid, stage = packet["paper_id"], packet["stage"]
        old = self.latest(pid, stage)
        value = {"decision_id": "SD-" + uuid.uuid4().hex, "project_id": self.state["project_id"], "paper_id": pid,
                 "protocol_version": current["protocol_version"], "screening_criteria_version": current["version"],
                 "candidate_set_version": current["candidate_set_version"], "screening_stage": stage,
                 "source_basis": packet["source_basis"], "decision": proposal["decision"], "review_role": proposal.get("review_role"),
                 "reason_codes": proposal.get("reason_codes", []), "explanation": proposal.get("explanation", ""),
                 "reviewer_type": "model", "reviewer_id": proposal.get("reviewer_id", "Codex"), "review_timestamp": utc_now(),
                 "document_id": packet["document_id"], "uncertainty_flags": proposal.get("uncertainty_flags", []),
                 "approval_status": "proposed", "superseded_decision_id": proposal.get("superseded_decision_id"),
                 "packet_id": packet["packet_id"], "criteria_ids": proposal.get("criteria_ids", []),
                 "source_facts": proposal.get("source_facts", []), "previous_stage_id": packet["previous_stage_id"], "review_note": ""}
        # Stable replay key excludes generated identity/time; a repeat cannot silently replace a reviewed record.
        key = digest(proposal)
        for decision in self.data["decisions"]:
            if decision.get("proposal_key") == key:
                return {**decision, "replayed": True, "effective_status": "stale" if self.stale(decision) else "current"}
        if old and value["superseded_decision_id"] != old["decision_id"]:
            raise ValueError("EXPLICIT_SUPERSESSION_REQUIRED")
        if not old and value["superseded_decision_id"]:
            raise ValueError("INVALID_SUPERSESSION")
        self.check(value, require_version=True)
        if self.stale(value):
            raise ValueError("STALE_SCREENING_CONTEXT")
        value["proposal_key"] = key
        self.data["decisions"].append(value)
        self.save("screening_proposal_imported")
        return value

    def check(self, value, require_version=False):
        validate_decision(value)
        packet = self.packet(value["packet_id"])
        version = self.data["criteria"][value["screening_criteria_version"] - 1]
        if value["project_id"] != self.state["project_id"] or value["protocol_version"] != version["protocol_version"] or packet["criteria_version"] != version["version"] or value["candidate_set_version"] != packet["candidate_set_version"]:
            raise ValueError("DECISION_VERSION_BINDING_MISMATCH")
        if any(value[k] != packet[p] for k, p in (("paper_id", "paper_id"), ("screening_stage", "stage"), ("document_id", "document_id"), ("source_basis", "source_basis"), ("previous_stage_id", "previous_stage_id"))):
            raise ValueError("DECISION_PACKET_BINDING_MISMATCH")
        rules = self.rules_for(version, value["paper_id"], value["screening_stage"])
        if (rules and not value["criteria_ids"]) or set(value["criteria_ids"]) - set(rules) or (not rules and value["decision"] in {"include", "exclude"}):
            raise ValueError("APPLICABLE_CRITERIA_IDS_REQUIRED")
        if value["decision"] == "include" and (value["review_role"] not in version["roles"] or set(value["criteria_ids"]) != set(rules)):
            raise ValueError("INCLUSION_ROLE_AND_ALL_APPLICABLE_CRITERIA_REQUIRED")
        if value["decision"] != "include" and value["review_role"] is not None:
            raise ValueError("ROLE_ONLY_FOR_INCLUSION")
        texts = {"title": packet["basic_metadata"].get("title") or ""}
        if value["screening_stage"] == "abstract":
            texts["abstract"] = packet["abstract"]["text"] or ""
            if not texts["abstract"] and value["decision"] in {"include", "exclude"}:
                raise ValueError("MISSING_ABSTRACT_REQUIRES_UNCERTAIN_OR_DEFER")
            if value["decision"] in {"include", "exclude"} and not any(f.get("location") == "abstract" for f in value["source_facts"]):
                raise ValueError("ABSTRACT_SOURCE_FACT_REQUIRED")
        if value["screening_stage"] == "fulltext_eligibility":
            texts = {str(p["pdf_page"]): p.get("text", "") for p in packet["pages"]}
            if value["decision"] in {"include", "exclude"} and packet["eligibility_status"] != "available_not_yet_assessed":
                raise ValueError("UNAVAILABLE_OR_WRONG_FULLTEXT_REQUIRES_UNCERTAIN_OR_DEFER")
            if value["decision"] in {"include", "exclude"}:
                # A registered paper_id is not PDF identity verification. Require an exact identity passage.
                identity = [f for f in value["source_facts"] if f.get("purpose") == "identity"]
                r = packet["basic_metadata"]
                if not any((r.get("doi") and r["doi"].casefold() in f.get("quote", "").casefold()) or normalize_title(r["title"]) in normalize_title(f.get("quote", "")) for f in identity):
                    raise ValueError("DOCUMENT_IDENTITY_PASSAGE_REQUIRED")
                if not any(f.get("purpose") == "eligibility" for f in value["source_facts"]):
                    raise ValueError("ELIGIBILITY_PASSAGE_REQUIRED")
                if require_version and not any(f.get("purpose") == "version" for f in value["source_facts"]):
                    raise ValueError("DOCUMENT_VERSION_PASSAGE_REQUIRED")
        for fact in value["source_facts"]:
            if not isinstance(fact, dict) or not fact.get("quote") or fact["quote"] not in texts.get(str(fact.get("location")), ""):
                raise ValueError("SOURCE_FACT_NOT_IN_PERMITTED_EVIDENCE")
        if value["decision"] in {"include", "exclude"} and not value["source_facts"]:
            raise ValueError("EXACT_SOURCE_FACT_REQUIRED")
        if value["decision"] == "exclude" and "criterion_not_met" not in value["reason_codes"] and "related_version" not in value["reason_codes"]:
            raise ValueError("EXCLUSION_REASON_REQUIRED")

    def review(self, decision_id, action, by, note, changes=None):
        self.authorize()
        self.require_criteria_approval()
        if self.context().get("mode") == "isolated_screening":
            raise ValueError("PILOT_CANNOT_RECORD_RESEARCH_APPROVAL")
        if not by.strip() or not note.strip() or action not in {"approve", "override", "reject", "uncertain", "defer", "reopen"}:
            raise ValueError("EXPLICIT_NAMED_REVIEW_REQUIRED")
        previous = next((d for d in self.data["decisions"] if d["decision_id"] == decision_id), None)
        if previous is None:
            raise ValueError("UNKNOWN_DECISION_ID")
        if previous != self.latest(previous["paper_id"], previous["screening_stage"]):
            raise ValueError("REVIEW_CURRENT_DECISION_ONLY")
        if self.stale(previous) and action != "reopen":
            raise ValueError("RESCREEN_STALE_DECISION_FIRST")
        value = {**previous, "decision_id": "SD-" + uuid.uuid4().hex, "reviewer_type": "human_declared", "reviewer_id": by,
                 "review_timestamp": utc_now(), "approval_status": "approved", "review_note": note,
                 "superseded_decision_id": decision_id, "identity_authenticated": False}
        value.pop("proposal_key", None)
        if action == "override":
            if not changes or set(changes) - {"decision", "review_role", "reason_codes", "explanation", "source_facts", "uncertainty_flags"}:
                raise ValueError("VALID_OVERRIDE_CHANGES_REQUIRED")
            value.update(changes)
        elif action in {"reject", "uncertain", "defer", "reopen"}:
            value.update(decision="defer" if action == "defer" else "uncertain", review_role=None,
                         reason_codes=["human_reopened" if action == "reopen" else "insufficient_information"], explanation=note)
            if action == "reopen":
                value["approval_status"] = "reopened"
        self.check(value, require_version=True)
        self.data["decisions"].append(value)
        self.save("screening_human_" + action)
        return value

    def stale(self, decision, seen=None):
        seen = set() if seen is None else seen
        if decision["decision_id"] in seen:
            return True
        seen.add(decision["decision_id"])
        current = self.current()
        old = self.data["criteria"][decision["screening_criteria_version"] - 1]
        pid, stage = decision["paper_id"], decision["screening_stage"]
        packet = self.packet(decision["packet_id"])
        if stage == "fulltext_eligibility" and decision["decision"] in {"include", "exclude"} and not any(f.get("purpose") == "version" for f in decision["source_facts"]):
            return True
        if digest(self.context()) != old["protocol_sha256"] or pid not in current["candidate_ids"]:
            return True
        if packet["registry_sha256"] != digest(self.registry.data["records"].get(pid)):
            return True
        if self.rules_for(old, pid, stage) != self.rules_for(current, pid, stage) or old["roles"] != current["roles"] or old["accepted_versions"] != current["accepted_versions"]:
            return True
        if stage != "title":
            prior = self.latest(pid, STAGES[STAGES.index(stage) - 1])
            if not prior or prior["decision_id"] != packet["previous_stage_id"] or prior["decision"] == "exclude" or self.stale(prior, seen):
                return True
        if "abstract" in packet and packet["abstract"].get("raw_response_path"):
            if checksum(safe_path(self.root, packet["abstract"]["raw_response_path"])) != packet["abstract"]["raw_sha256"]:
                return True
        if packet["document_id"]:
            from ..documents.pipeline import DocumentPipeline
            pipe = DocumentPipeline(self.root)
            doc, _ = pipe._document_file(pipe.store.load(), packet["document_id"])
            if doc["sha256"] != packet["document_sha256"] or doc["version_kind"] != packet["version_kind"] or doc["paper_id"] != pid or doc["access_basis"] != packet["access_basis"]:
                return True
            if packet.get("parser_version") and packet["parser_version"] != parser_version():
                return True
        return False

    def queue(self):
        result = []
        for pid in self.current()["candidate_ids"]:
            latest = self.latest(pid)
            result.append({"paper_id": pid, "decision_id": latest["decision_id"] if latest else None,
                           "stage": latest["screening_stage"] if latest else "title", "decision": latest["decision"] if latest else "not_screened",
                           "approval_status": latest["approval_status"] if latest else "pending", "stale": self.stale(latest) if latest else False,
                           "final": bool(latest and not self.stale(latest) and latest["approval_status"] == "approved" and
                                         (latest["decision"] == "exclude" or (latest["decision"] == "include" and latest["screening_stage"] == "fulltext_eligibility")))})
        return result

    def acquisition(self):
        docs = DocumentStore(self.root).load()
        review_path = self.root / "03_library/ACQUISITION_REVIEW.json"
        review = read(review_path).get("papers", {}) if review_path.exists() else {}
        rows = []
        for pid, r in self.registry.data["records"].items():
            versions = [d for d in docs["documents"].values() if d["paper_id"] == pid]
            attempts = [a for a in docs["attempts"].values() if a["paper_id"] == pid]
            for doc in versions or [None]:
                valid = bool(doc and safe_path(self.root, doc["local_path"]).exists() and checksum(safe_path(self.root, doc["local_path"])) == doc["sha256"])
                assessment = self.latest(pid, "fulltext_eligibility")
                assessed = bool(assessment and doc and assessment["document_id"] == doc["document_id"])
                rows.append({"paper_id": pid, "bibliographic_registration": "registered", "identity_verification": r.get("verification_status", "unknown"),
                    "fulltext_availability": "available" if valid else ("local_document_invalid" if doc else review.get(pid, {}).get("status", "not_requested")),
                    "document_id": doc["document_id"] if doc else None, "document_version": doc["version_kind"] if doc else None,
                    "acquisition_attempt_status": attempts[-1]["result_status"] if attempts else "not_attempted",
                    "rights_access_status": doc["access_basis"] if doc else "unknown", "license_status": doc["license_status"] if doc else "unknown",
                    "local_document_reference": doc["local_path"] if doc else None, "parser_status": doc["parsing_status"] if doc else "not_parsed",
                    "eligibility_status": ("assessed_" + assessment["approval_status"] if assessed else "not_assessed"),
                    "remaining_action": "targeted_eligibility_and_human_review" if valid else "authorized_import_or_explicit_disposition",
                    "human_review_required": True})
        return rows

    def coverage(self):
        queue = self.queue()
        decisions = [self.latest(q["paper_id"]) for q in queue if q["decision_id"]]
        upstream = self.root / "02_discovery/EXPANSION_CANDIDATES.json"
        external = read(upstream) if upstream.exists() else []
        if isinstance(external, dict):
            external = external.get("candidates", external)
        if isinstance(external, dict):
            external = list(external.values())
        unresolved = sum(not d.get("resolved_paper_id", d.get("paper_id")) for d in external if isinstance(d, dict))
        counts = {"total_registered": len(self.registry.data["records"]), "related_version_records": sum(bool(r.get("related_versions")) for r in self.registry.data["records"].values()),
                  "eligible_candidates": len(queue), "scope_exception_records": len(self.current()["scope_exceptions"]),
                  "upstream_unresolved_candidates": unresolved, "final_records": sum(q["final"] for q in queue),
                  "pending_review": sum(not q["final"] for q in queue), "human_reviewed": sum(d["reviewer_type"] == "human_declared" for d in decisions),
                  "uncertain": sum(d["decision"] == "uncertain" for d in decisions), "deferred": sum(d["decision"] == "defer" for d in decisions),
                  "stale": sum(q["stale"] for q in queue), "not_screened": sum(not q["decision_id"] for q in queue),
                  "missing_abstracts": sum(not self.abstract(pid)["text"] for pid in self.current()["candidate_ids"]),
                  "fulltext_unavailable": len(set(self.current()["candidate_ids"]) - {r["paper_id"] for r in self.acquisition() if r["fulltext_availability"] == "available"})}
        for stage in STAGES:
            counts[stage + "_screened"] = sum(bool(self.latest(pid, stage)) for pid in self.current()["candidate_ids"])
        counts["proposed_included_by_role"] = dict(Counter(d["review_role"] for d in decisions if d["decision"] == "include"))
        counts["fulltext_inspected_records"] = sum(bool(self.latest(pid, "fulltext_eligibility") and self.packet(self.latest(pid, "fulltext_eligibility")["packet_id"])["eligibility_status"] == "available_not_yet_assessed") for pid in self.current()["candidate_ids"])
        finals = [self.latest(q["paper_id"]) for q in queue if q["final"]]
        counts["final_included_by_role"] = dict(Counter(d["review_role"] for d in finals if d["decision"] == "include"))
        counts["final_excluded_by_primary_reason"] = dict(Counter(d["reason_codes"][0] for d in finals if d["decision"] == "exclude"))
        counts["proposed_excluded_by_primary_reason"] = dict(Counter(d["reason_codes"][0] for d in decisions if d["decision"] == "exclude"))
        counts["reconciled"] = counts["final_records"] + counts["pending_review"] == len(queue) and len(queue) + counts["scope_exception_records"] == counts["total_registered"]
        return counts

    def export_acquisition(self):
        rows = self.acquisition()
        if self.data["criteria"]:
            self.export()
        else:
            path = self.root / "03_library/ACQUISITION_STATUS.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["paper_id"])
                writer.writeheader()
                writer.writerows(rows)
        return {"records": rows, "path": "03_library/ACQUISITION_STATUS.csv", "meaning": "Availability, not eligibility or completed reading"}

    def validate(self):
        errors = []
        try:
            self.check_journal()
            current = self.current()
            if current["protocol_sha256"] != digest(self.context()):
                errors.append("PROTOCOL_AMENDMENT_DETECTED")
            now = {pid: digest(r) for pid, r in self.registry.data["records"].items()}
            if now != current["registry_snapshot"]:
                errors.append("CANDIDATE_REGISTRY_CHANGED_REVIEW_SCOPE_REQUIRED")
            seen = set()
            for d in self.data["decisions"]:
                self.check(d)
                if d["decision_id"] in seen or (d["superseded_decision_id"] and d["superseded_decision_id"] not in seen):
                    errors.append("INVALID_DECISION_HISTORY")
                seen.add(d["decision_id"])
            for ref in self.data["packets"].values():
                if checksum(safe_path(self.root, ref["path"])) != ref["sha256"]:
                    errors.append("PACKET_CHECKSUM_MISMATCH")
            for rel, sha in self.data["exports"].items():
                if not safe_path(self.root, rel).exists() or checksum(safe_path(self.root, rel)) != sha:
                    errors.append("EXPORT_CHECKSUM_MISMATCH:" + rel)
            acq_path = self.root / "03_library/ACQUISITION_STATUS.csv"
            if acq_path.exists():
                with acq_path.open(newline="", encoding="utf-8") as handle:
                    recorded = list(csv.DictReader(handle))
                expected = [{k: "" if v is None else str(v) for k, v in row.items()} for row in self.acquisition()]
                if recorded != expected:
                    errors.append("ACQUISITION_LEDGER_STALE: screening-recover regenerates derived views")
            for q in self.queue():
                if q["stale"]:
                    errors.append("STALE_DECISION:" + q["paper_id"])
        except (ValueError, OSError, KeyError, TypeError, IndexError, StopIteration) as exc:
            errors.append(str(exc))
        return {"valid": not errors, "errors": errors}

    def gate(self, require_completed=True):
        validation = self.validate()
        blockers, warnings = [], []
        eligible = []
        try:
            blockers += self.upstream()
            current = self.current()
            if not any(a["criteria_sha256"] == digest(current) for a in self.data["approvals"]):
                blockers.append("CURRENT_CRITERIA_AND_SCOPE_HUMAN_APPROVAL_REQUIRED")
            queue = self.queue()
            blockers += ["UNRESOLVED_OR_PENDING_REVIEW:" + q["paper_id"] for q in queue if not q["final"]]
            if not queue:
                blockers.append("EMPTY_CANDIDATE_SET")
            if require_completed and self.state["phases"]["6"]["status"] != "completed":
                blockers.append("PHASE6_INCOMPLETE")
            eligible = [q["paper_id"] for q in queue if q["final"] and q["decision"] == "include"]
            if current["scope_exceptions"]:
                warnings.append("BOUNDED_SCOPE_EXCEPTIONS_PRESENT")
            if self.coverage()["upstream_unresolved_candidates"]:
                warnings.append("UPSTREAM_UNRESOLVED_CITATIONS_RETAINED_OUTSIDE_CANONICAL_SCOPE")
        except (ValueError, OSError, KeyError, TypeError) as exc:
            blockers.append(str(exc))
        status = "fail" if not validation["valid"] else "blocked" if blockers else "warn" if warnings else "pass"
        return {"status": status, "allowed": status in {"pass", "warn"}, "errors": validation["errors"],
                "blockers": blockers, "warnings": warnings, "eligible_paper_ids": eligible if status in {"pass", "warn"} else [],
                "identity_authenticated": False, "automatic_phase_completion": False,
                "assessment_sha256": digest({"data": {k: v for k, v in self.data.items() if k != "exports"}, "upstream": blockers})}

    def export(self):
        if not self.data["criteria"]:
            return
        base = self.root / "04_screening"
        base.mkdir(parents=True, exist_ok=True)
        latest = [self.latest(pid, stage) for pid in self.current()["candidate_ids"] for stage in STAGES]
        latest = [d for d in latest if d]
        generated = {}
        def emit(relative, text):
            # Projections are disposable; the event journal retains immutable history.
            path = safe_path(self.root, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            generated[relative] = checksum(path)
        def table(relative, rows, fields):
            out = io.StringIO(newline="")
            writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows({k: canonical_json(v) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in rows)
            emit(relative, out.getvalue())
        table("04_screening/SCREENING_MASTER.csv", latest, FIELDS)
        table("04_screening/EXCLUSION_LOG.csv", [d for d in self.data["decisions"] if d["decision"] == "exclude"], FIELDS)
        table("04_screening/FULLTEXT_ELIGIBILITY_LOG.csv", [d for d in self.data["decisions"] if d["screening_stage"] == "fulltext_eligibility"], FIELDS)
        emit("04_screening/SCREENING_DECISION_HISTORY.jsonl", "".join(canonical_json(d) + "\n" for d in self.data["decisions"]))
        emit("04_screening/SCREENING_CRITERIA_VERSION.json", json.dumps({"versions": self.data["criteria"], "approvals": self.data["approvals"]}, ensure_ascii=False, indent=2) + "\n")
        acq = self.acquisition()
        table("03_library/ACQUISITION_STATUS.csv", acq, list(acq[0]) if acq else ["paper_id"])
        emit("04_screening/SCREENING_COVERAGE_REPORT.md", "# Screening coverage\n\nProposals are not final inclusion; stages are cumulative, not additive.\n\n```json\n" + json.dumps(self.coverage(), indent=2) + "\n```\n")
        self.data["exports"] = generated
        state = load_state(self.root)
        state["screening_data"] = self.data
        self.state = persist_state(self.root, state, "screening_exports_written")
        # Informational snapshot only; Gate 1 always recomputes from authoritative records.
        write_json_atomic(base / "GATE1_VALIDATION_REPORT.json", self.gate())

    def recover(self):
        recover_state(self.root)
        self.__init__(self.root)
        self.export()
        return {"status": "recovered", "validation": self.validate()}
