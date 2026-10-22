"""Offline manual-search materials. Never a provider, importer or approval mechanism."""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from ..state import utc_now

RELATIVE_DIR = Path("02_discovery/manual/google_scholar")
FIELDS = ["candidate_id", "session_id", "title", "authors", "year", "doi", "url",
          "source", "verification_status", "verification_basis", "possible_duplicate_paper_ids",
          "duplicate_status", "needs_screening", "import_status", "notes"]


def validate_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError("SCHOLAR_PLAN_MUST_BE_OBJECT")
    for field in ("research_question", "suitability", "rationale", "coverage_gaps", "year_filter", "stop_rule"):
        if not isinstance(plan.get(field), str) or not plan[field].strip():
            raise ValueError(f"SCHOLAR_PLAN_REQUIRED: {field}")
    if plan["suitability"] not in {"recommended", "optional", "not_recommended"}:
        raise ValueError("SCHOLAR_SUITABILITY_INVALID")
    queries = plan.get("queries", [])
    if not isinstance(queries, list) or not 3 <= len(queries) <= 5:
        raise ValueError("SCHOLAR_REQUIRES_3_TO_5_QUERIES")
    ids, strings = set(), set()
    for q in queries:
        if not isinstance(q, dict) or any(not isinstance(q.get(k), str) or not q[k].strip()
                                         for k in ("id", "query", "purpose")):
            raise ValueError("SCHOLAR_QUERY_FIELDS_REQUIRED")
        if q["id"] in ids or q["query"] in strings or q["query"].count('"') % 2:
            raise ValueError("SCHOLAR_DUPLICATE_OR_UNBALANCED_QUERY")
        if type(q.get("max_results_to_check")) is not int or not 1 <= q["max_results_to_check"] <= 1000:
            raise ValueError("SCHOLAR_RESULT_SCOPE_REQUIRED")
        ids.add(q["id"])
        strings.add(q["query"])
    # Semantic suitability/syntax review remains an Agent/human task, not this schema check.
    return plan


GUIDE = """# Google Scholar 人工补充检索：新手操作与核对表

状态：尚未执行。此材料不访问 Scholar，不代表来源授权、科研审批或检索充分性。

1. 先看 SEARCH_PLAN.md：核对研究问题、补充价值、年份、每条检查上限和停止规则；由用户确认范围后手动操作。
2. 打开 https://scholar.google.com ，逐条复制检索式。双引号用于短语；普通词以空格组合。不照搬 PubMed 字段标签或复杂数据库布尔嵌套。
3. 按已批准年份范围使用年份/自定义范围或高级检索；记录实际年份设置和排序，不把“按日期”与“按相关性”混为一谈。
4. 每条只检查约定范围。记录日期、查询原文、实际检查结果位置、结果数、排序、停止理由；排名会变化，不能保证重现完全相同列表。
5. Cited by 是引用此文的文献；Related articles 是相似文献；All versions 用于核查同一成果的其他版本。不要把版本数或引用次数当作独立研究数。额外追踪须先约定种子与检查上限，单独留记录；本模板不自动执行。
6. 候选写入 RESULTS.csv：真实题名、作者、年份、DOI 或链接。不确定的字段留空并在 notes 解释；来源核验不能只靠搜索片段。缺 DOI 不等于排除。
7. 与已有 Registry 按 DOI、题名、作者、年份比较；疑似重复填 possible_duplicate_paper_ids 和 duplicate_status，不直接合并或修改 Registry。所有候选仍需要正式 Screening。
8. 看到验证码、访问限制或预算到达就停止并记录，不绕过限制。全文仅按公开许可或本人合法权限另行获取，本步骤不下载 PDF。

## 实际完成后才填写

- [ ] SESSIONS.json 增加人工操作记录；空 sessions 表示 not_performed。
- [ ] 每条记录包含 session_id、query_id、exact_query、date (YYYY-MM-DD)、year_filter、sort、first_result、last_result、checked_count、stop_reason、record_source（例如用户实际提交的记录说明）。
- [ ] checked_count 为实际检查条数，位置从 1 开始；确实零结果时三项数字都填 0，stop_reason 写 observed_zero_results。不能把未执行记作零结果。
- [ ] RESULTS.csv 的 source 写 google_scholar；verification_status 用 unverified / verified / uncertain，verified 必须有 verification_basis。缺失作者/年份要在 notes 标明。
- [ ] duplicate_status 用 unresolved / possible_duplicate / checked_no_match；后者只表示本次本地核对未匹配，不证明全球唯一。
- [ ] needs_screening 保持 true；import_status 保持 not_imported。本模块不导入、不批准、不认证操作者身份。
- [ ] 保存原始人工操作记录，勿覆盖旧记录。重新生成覆盖报告使用新文件名，不能靠勾选本清单宣称完成。

记录只能反映用户报告的操作。Coverage 的 performed_as_reported 不表示所有计划已做完、覆盖充分或已经独立审核。
检索式若要调整，保留原计划、另建版本；本轮 CSV/JSON 只接受计划内原查询的普通结果检查。
Cited by / Related articles 的额外分支记录目前需另存人工日志，不会自动计入此模块统计。

## 可选工具

Google Scholar Button 可辅助从当前网页查找论文，并非必需。只从官方商店获取，先自行检查权限；Agent 不安装扩展、不读取私人浏览器内容。

参考： [Google Scholar 官方帮助](https://scholar.google.com/intl/en/scholar/help.html)；
[官方 Button 商店页](https://chromewebstore.google.com/detail/google-scholar-button/ldipcbpaocekfooobnbcddclnhejkcpn)。
Scholar 不提供这里可用的官方批量检索接口。本模块没有爬虫或网络传输代码。
"""


def prepare(plan, output: Path):
    """Render Agent-authored academic queries; do not infer them from keywords."""
    validate_plan(plan)
    output.mkdir(parents=True, exist_ok=False)
    saved = {**plan, "created_at": utc_now(), "execution_status": "not_performed",
             "provider": "google_scholar", "mode": "manual_supplementary",
             "query_authoring": "agent_or_researcher; semantic review required"}
    (output / "PLAN.json").write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Google Scholar Supplementary Search Plan", "", "状态：not_performed；待用户确认范围。",
             "", f"RQ: {plan['research_question']}", "", f"适用性：{plan['suitability']} — {plan['rationale']}",
             f"覆盖缺口：{plan['coverage_gaps']}", f"年份：{plan['year_filter']}", f"停止规则：{plan['stop_rule']}", ""]
    for q in plan["queries"]:
        lines.extend([f"## {q['id']}", "", f"`{q['query']}`", "", q["purpose"],
                      f"最多检查 {q['max_results_to_check']} 条结果位置；不是已检得数量。", ""])
    (output / "SEARCH_PLAN.md").write_text("\n".join(lines), encoding="utf-8")
    (output / "CHECKLIST_ZH.md").write_text(GUIDE, encoding="utf-8")
    (output / "SESSIONS.json").write_text('{"sessions": []}\n', encoding="utf-8")
    with (output / "RESULTS.csv").open("x", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=FIELDS).writeheader()
    return {"output": str(output), "execution_status": "not_performed", "queries": len(plan["queries"]),
            "network_requests": 0, "registry_imports": 0}


def manual_coverage(project: Path):
    root = project / RELATIVE_DIR
    result = {"provider": "google_scholar", "category": "Manual supplementary search",
              "status": "not_performed", "sessions_reported": 0, "candidate_observations": 0,
              "registry_imports": 0, "validation_errors": [], "planned_query_ids": [],
              "unperformed_query_ids": [], "completed_scope": "not_assessed",
              "verification": "user_reported_only; not authenticated or independently audited",
              "coverage_gaps": ["Manual search not performed; no coverage or saturation claim."]}
    if not root.exists():
        return result
    try:
        plan = validate_plan(json.loads((root / "PLAN.json").read_text(encoding="utf-8")))
        queries = {q["id"]: q for q in plan["queries"]}
        result["planned_query_ids"] = list(queries)
        result["unperformed_query_ids"] = list(queries)
        sessions = json.loads((root / "SESSIONS.json").read_text(encoding="utf-8"))["sessions"]
        if not isinstance(sessions, list):
            raise ValueError("sessions must be a list")
        valid = {}
        totals = {}
        for s in sessions:
            for key in ("session_id", "query_id", "exact_query", "date", "year_filter", "sort", "stop_reason", "record_source"):
                if not isinstance(s.get(key), str) or not s[key].strip():
                    raise ValueError(f"session field required: {key}")
            date.fromisoformat(s["date"])
            q = queries[s["query_id"]]
            if s["session_id"] in valid or s["exact_query"] != q["query"]:
                raise ValueError("duplicate session or query/plan mismatch")
            first, last, count = (s[k] for k in ("first_result", "last_result", "checked_count"))
            if any(type(n) is not int for n in (first, last, count)):
                raise ValueError("checked range must contain integers")
            if not ((first == last == count == 0 and s["stop_reason"] == "observed_zero_results") or
                    (1 <= first <= last <= q["max_results_to_check"] and 1 <= count <= last - first + 1)):
                raise ValueError("invalid checked range or scope exceeded")
            totals[s["query_id"]] = totals.get(s["query_id"], 0) + count
            if totals[s["query_id"]] > q["max_results_to_check"]:
                raise ValueError("cumulative planned scope exceeded")
            valid[s["session_id"]] = s
        with (root / "RESULTS.csv").open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDS:
                raise ValueError("result template columns mismatch")
            rows = list(reader)
        seen = set()
        for row in rows:
            if not row["candidate_id"] or row["candidate_id"] in seen or not row["title"].strip():
                raise ValueError("candidate identity/title missing or repeated")
            seen.add(row["candidate_id"])
            if row["session_id"] not in valid or not (row["doi"] or row["url"]):
                raise ValueError("candidate needs a performed session and DOI or URL")
            if valid[row["session_id"]]["checked_count"] == 0:
                raise ValueError("candidate cannot originate in zero-results session")
            if row["source"] != "google_scholar" or row["import_status"] != "not_imported" or row["needs_screening"] != "true":
                raise ValueError("manual candidate cannot claim import or screening approval")
            if row["verification_status"] not in {"unverified", "verified", "uncertain"} or (row["verification_status"] == "verified" and not row["verification_basis"]):
                raise ValueError("verification status/basis invalid")
            if row["duplicate_status"] not in {"unresolved", "possible_duplicate", "checked_no_match"}:
                raise ValueError("duplicate status invalid")
            if (not row["authors"] or not row["year"]) and not row["notes"]:
                raise ValueError("missing bibliographic fields require notes")
        performed = {s["query_id"] for s in valid.values()}
        result.update(status="performed_as_reported" if valid else "not_performed",
                      sessions_reported=len(valid), candidate_observations=len(rows),
                      checked_result_observations=sum(totals.values()),
                      unperformed_query_ids=[q for q in queries if q not in performed],
                      unresolved_identity_observations=sum(r["verification_status"] != "verified" for r in rows),
                      unresolved_duplicate_observations=sum(r["duplicate_status"] != "checked_no_match" for r in rows),
                      candidates=[{k: r[k] for k in ("candidate_id", "title", "doi", "url", "verification_status", "possible_duplicate_paper_ids", "duplicate_status", "import_status")} for r in rows],
                      coverage_gaps=[plan["coverage_gaps"], "Candidates are observations, not unique registered papers or included studies.",
                                     "Unchecked ranks, revised queries and citation/related branches are not accounted here; scope completion requires human review."])
        if not valid:
            result["coverage_gaps"].insert(0, "Manual search not performed; no coverage or saturation claim.")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, csv.Error) as exc:
        result["status"] = "invalid_records"
        result["validation_errors"].append(str(exc))
    return result
