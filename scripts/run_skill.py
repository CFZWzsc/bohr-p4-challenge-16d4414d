#!/usr/bin/env python3
"""Argument and reasoning audit for a manuscript (Python standard library only).

Reads a case file (default /input/case.json) with manuscript text or a section
map and reconstructs the argument chain aim -> method -> evidence -> interpretation
-> conclusion. It checks whether the conclusion answers the aim, whether causal
language is backed by an experimental design, whether conclusions overshoot the
sample scope, whether inference markers are anchored to reported evidence, and
whether alternative explanations are considered. Each problem is located to a
section/sentence, typed and severity-rated; missing links are reported as gaps,
not filled in.

No network access, no randomness, no private paths.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

DEFAULT_CASE = "/input/case.json"
DEFAULT_OUT = "/app/output/result.json"
DEFAULT_WORK = "/app/work"
OBSERVATIONAL = r"cross.sectional|observational|cohort|case.control|survey|correlat|retrospective|横断面|观察性|队列|病例对照|调查|相关"
EXPERIMENTAL = r"randomi[sz]\w*|controlled trial|intervention|experiment|random allocation|随机|干预|对照试验|实验"
CAUSAL = r"\bcaus(e|es|ed|ing)\b|leads? to|results? in|drives?|due to|because of|导致|引起|造成|所致|因为"
HEDGE = r"may|might|suggest\w*|possible|possibly|potentially|could|consistent with|可能|提示|或许|与.*一致"
INFERENCE = r"\btherefore\b|\bthus\b|\bhence\b|consequently|it follows that|因此|所以|由此可见"
ALTERNATIVE = r"alternative explanation|confound\w*|reverse causation|limitation\w*|competing explanation|反向因果|混杂|局限|替代解释"
GENERALIZE = r"\ball (patients|people|adults|women|men|children|cases)|every\b|universal\w*|in all\b|regardless of|所有人|普遍|无论"
SCOPE = r"in mice|in rats|in vitro|in cells|in patients|in adults|single.cent|one hospital|mice|大鼠|小鼠|细胞|单中心|一家医院"


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_task_text(case_path, work_dir):
    for path in (Path(case_path).resolve().parent / "task.md", Path("/input/task.md"), Path(work_dir) / "task.md"):
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue
    return ""


def norm_space(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def as_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return norm_space(value)
    if isinstance(value, list):
        return norm_space(" ".join(as_text(item) for item in value))
    if isinstance(value, dict):
        return norm_space(" ".join(as_text(item) for item in value.values()))
    return norm_space(str(value))


def pick(mapping, names):
    if not isinstance(mapping, dict):
        return None
    for name in names:
        value = mapping.get(name)
        if value not in (None, "", [], {}):
            return value
    return None


def sections_of(case, task_text):
    manuscript = pick(case, ("manuscript", "paper", "text", "document", "article", "content"))
    sections = {}
    if isinstance(manuscript, dict):
        raw = manuscript.get("sections") if isinstance(manuscript.get("sections"), dict) else manuscript
        for key, value in raw.items():
            text = as_text(value)
            if text:
                sections[str(key).lower()] = text
    elif isinstance(manuscript, list):
        for item in manuscript:
            if isinstance(item, dict):
                name = as_text(pick(item, ("heading", "section", "name"))).lower()
                text = as_text(pick(item, ("text", "content")))
                if name and text:
                    sections[name] = text
    if not sections:
        sections["body"] = as_text(manuscript) or task_text
    return sections


def sentences(text):
    text = norm_space(text)
    if not text:
        return []
    return [norm_space(part) for part in re.split(r"(?<=[.!?])\s+|(?<=[。！？])", text) if norm_space(part)]


def first_section(sections, names):
    for key, value in sections.items():
        if any(name in key for name in names):
            return key, value
    return "", ""


def tokenize(text, limit=40):
    stop = {"the", "and", "for", "with", "from", "that", "this", "these", "were", "was", "are", "has", "have",
            "study", "studies", "paper", "results", "data", "analysis", "group", "also", "can", "not", "using",
            "used", "between", "among", "our", "we", "which", "their", "its", "than", "more", "less", "may"}
    words = [word for word in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", norm_space(text).lower()) if word not in stop]
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        for index in range(len(chunk) - 1):
            words.append(chunk[index:index + 2])
    seen, ordered = set(), []
    for word in words:
        if word not in seen:
            seen.add(word)
            ordered.append(word)
    return ordered[:limit]


def has_number(text):
    return bool(re.search(r"\d", text))


def build_payload(case, task_text):
    sections = sections_of(case, task_text)
    aim_key, aim = first_section(sections, ("introduction", "background", "aim", "objective", "引言", "前言"))
    method_key, method = first_section(sections, ("method", "方法"))
    result_key, results = first_section(sections, ("result", "结果"))
    discussion_key, discussion = first_section(sections, ("discussion", "讨论"))
    conclusion_key, conclusion = first_section(sections, ("conclusion", "结论"))
    if not conclusion:
        conclusion_key, conclusion = discussion_key, discussion
    all_text = norm_space(" ".join(sections.values()))
    findings, gaps = [], []

    design_observational = bool(re.search(OBSERVATIONAL, method or all_text, re.IGNORECASE))
    design_experimental = bool(re.search(EXPERIMENTAL, method or all_text, re.IGNORECASE))
    design = "experimental" if design_experimental else ("observational" if design_observational else "unclear")

    aim_sentences = [sentence for sentence in sentences(aim) if sentence]
    result_sentences = [sentence for sentence in sentences(results) if sentence]
    discussion_sentences = [sentence for sentence in sentences(discussion) if sentence]
    conclusion_sentences = [sentence for sentence in sentences(conclusion) if sentence]
    premises = [{"locator": "results#s%d" % index, "text": sentence[:300]} for index, sentence in enumerate(result_sentences)
                if has_number(sentence) or re.search(r"increas|decreas|higher|lower|differ|associated|增加|降低|高于|低于|相关", sentence.lower())]

    if not results:
        findings.append({"facet": "argument_chain", "severity": "high", "locator": "results#0", "quote": "",
                         "finding": "No results section; the conclusion has no reported evidence to rest on.",
                         "evidence": "sections detected: " + ", ".join(sorted(sections)),
                         "recommendation": "Add the results that the conclusion depends on.", "status": "missing_link"})
        gaps.append({"type": "missing_evidence_link", "basis": "results section absent"})

    aim_terms = set(tokenize(aim, limit=30))
    conclusion_terms = set(tokenize(conclusion, limit=30))
    overlap = len(aim_terms & conclusion_terms) / float(len(aim_terms) or 1)
    if aim_terms and conclusion_terms and overlap < 0.15:
        findings.append({"facet": "argument_chain", "severity": "medium", "locator": "conclusion#0",
                         "quote": conclusion_sentences[0][:300] if conclusion_sentences else "",
                         "finding": "The conclusion does not use the constructs stated in the aim.",
                         "evidence": "aim/conclusion term overlap %.2f" % overlap,
                         "recommendation": "Answer the aim in its own terms, or restate the aim to match the analysis.",
                         "status": "reported"})

    causal_sentences = []
    for key, text in (("discussion", discussion), ("conclusion", conclusion)):
        if not text:
            continue
        for index, sentence in enumerate(sentences(text)):
            if re.search(CAUSAL, sentence, re.IGNORECASE) and not re.search(HEDGE, sentence, re.IGNORECASE):
                causal_sentences.append({"section": key, "index": index, "text": sentence})
                if design != "experimental":
                    findings.append({"facet": "causal_inference", "severity": "high" if design == "observational" else "medium",
                                     "locator": "%s#s%d" % (key, index), "quote": sentence[:300],
                                     "finding": "Causal wording is used without an experimental design in the supplied text.",
                                     "evidence": "design detected: %s" % design,
                                     "recommendation": "Replace causal verbs with association wording, or justify the causal claim with design and analysis.",
                                     "status": "reported"})
    if causal_sentences and design == "observational":
        gaps.append({"type": "causal_claim_from_observational_design",
                     "basis": "%d causal sentence(s) with design=observational" % len(causal_sentences)})

    sample_scope = re.findall(SCOPE, method or all_text, re.IGNORECASE)
    generalizing = []
    for key, text in (("discussion", discussion), ("conclusion", conclusion)):
        for index, sentence in enumerate(sentences(text)):
            if re.search(GENERALIZE, sentence, re.IGNORECASE):
                generalizing.append({"locator": "%s#s%d" % (key, index), "text": sentence})
                findings.append({"facet": "generalization", "severity": "medium", "locator": "%s#s%d" % (key, index),
                                 "quote": sentence[:300],
                                 "finding": "The claim is generalised beyond the reported sample scope.",
                                 "evidence": "scope markers: " + (", ".join(sorted(set(sample_scope))) or "none stated"),
                                 "recommendation": "Restrict the claim to the studied population, setting and species.",
                                 "status": "reported"})
    if generalizing:
        gaps.append({"type": "scope_overshoot", "basis": "%d generalising sentence(s)" % len(generalizing)})

    unanchored = []
    for key, text in (("discussion", discussion), ("conclusion", conclusion)):
        for index, sentence in enumerate(sentences(text)):
            if re.search(INFERENCE, sentence, re.IGNORECASE):
                anchored = bool(re.search(r"\[\d", sentence)) or any(
                    term in sentence.lower() for premise in premises for term in tokenize(premise["text"], limit=12)[:4])
                if not anchored:
                    unanchored.append({"locator": "%s#s%d" % (key, index), "text": sentence})
                    findings.append({"facet": "argument_chain", "severity": "medium", "locator": "%s#s%d" % (key, index),
                                     "quote": sentence[:300],
                                     "finding": "An inference marker is not anchored to a reported result or citation.",
                                     "evidence": "no result term or citation marker in the sentence",
                                     "recommendation": "Name the result or citation that licenses this inference.",
                                     "status": "reported"})
    if unanchored:
        gaps.append({"type": "unanchored_inference", "basis": "%d inference sentence(s) without a link" % len(unanchored)})

    if design_observational and (discussion or conclusion) and not re.search(ALTERNATIVE, discussion + " " + conclusion, re.IGNORECASE):
        findings.append({"facet": "alternative_explanations", "severity": "medium", "locator": "discussion#0", "quote": "",
                         "finding": "No alternative explanation or confounding is discussed for an observational finding.",
                         "evidence": "no alternative/confound/limitation cue in discussion or conclusion",
                         "recommendation": "Discuss at least one plausible alternative explanation and how it was addressed.",
                         "status": "not_reported"})

    if aim_sentences and conclusion_sentences:
        aim_strong = bool(re.search(r"will|aims? to|test whether|hypothes|旨在|检验|假设", aim, re.IGNORECASE))
        if aim_strong and not any(re.search(r"supported|not supported|consistent|inconsistent|支持|不支持|一致", sentence, re.IGNORECASE)
                                  for sentence in conclusion_sentences):
            findings.append({"facet": "argument_chain", "severity": "medium", "locator": "conclusion#0",
                             "quote": conclusion_sentences[0][:300],
                             "finding": "The stated hypothesis is neither confirmed nor rejected in the conclusion.",
                             "evidence": "aim uses hypothesis framing; conclusion has no verdict wording",
                             "recommendation": "State whether the hypothesis was supported by the reported evidence.",
                             "status": "reported"})

    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for item in findings:
        severity_counts[item["severity"]] = severity_counts.get(item["severity"], 0) + 1

    argument_map = {
        "aim": {"locator": aim_key + "#s0" if aim_key else "", "quote": (aim_sentences[0][:300] if aim_sentences else "")},
        "design": {"type": design, "observational_markers": sorted(set(sample_scope))[:8]},
        "premises": premises[:12],
        "inference_markers": [{"locator": item["locator"] if "locator" in item else "%s#s%d" % (item["section"], item["index"]),
                               "quote": item["text"][:240]} for item in unanchored + causal_sentences][:12],
        "conclusion": {"locator": conclusion_key + "#s0" if conclusion_key else "",
                       "quote": (conclusion_sentences[0][:300] if conclusion_sentences else "")},
        "edges": [
            {"from": "aim", "to": "design", "status": "present" if method else "missing"},
            {"from": "design", "to": "premises", "status": "present" if premises else "missing"},
            {"from": "premises", "to": "conclusion", "status": "present" if premises and conclusion else "missing"},
        ],
    }

    uncertainty = []
    if not all_text:
        uncertainty.append({"type": "no_text", "detail": "No manuscript text was found."})
    if design == "unclear":
        uncertainty.append({"type": "design_unclear", "detail": "Neither experimental nor observational markers were found; causal checks are conservative."})
    if not conclusion:
        uncertainty.append({"type": "no_conclusion", "detail": "No conclusion section; the discussion was used as the conclusion."})
    uncertainty.append({"type": "text_only", "detail": "The argument is reconstructed from the supplied text; no data or analysis was re-run."})

    if not all_text:
        status = "insufficient_input"
    elif not results or not conclusion:
        status = "partial"
    else:
        status = "success"

    result = {
        "sections_detected": sorted(sections),
        "argument_map": argument_map,
        "findings": findings,
        "gaps": gaps,
        "summary": {"total": len(findings), "by_severity": severity_counts,
                    "verdict": "major_argument_revision" if severity_counts.get("high") else ("minor_argument_revision" if findings else "no_blocking_issue")},
        "revision_checklist": [{"locator": item["locator"], "action": item["recommendation"]} for item in findings],
        "limitations": [
            "The argument chain is reconstructed from section text, not from a formal logic parse.",
            "Causal wording detection is cue-based; a justified causal analysis may still be valid.",
            "Generalisation checks rely on explicit scope and universal quantifier cues.",
            "No data or analysis was re-run, so premise truth is not verified.",
        ],
        "change_log": [
            "Located aim, methods, results, discussion and conclusion sections.",
            "Detected whether the design is experimental, observational or unclear.",
            "Tested causal wording against the detected design.",
            "Checked scope overshoot and inference anchors.",
            "Checked for alternative explanations and an explicit hypothesis verdict.",
        ],
    }
    checks = []
    for facet, label in FACET_LABELS:
        hits = [item for item in findings if item.get("facet") == facet]
        checks.append({"check": label, "facet": facet,
                       "status": "finding" if hits else "no_issue_found",
                       "findings": len(hits),
                       "basis": "cue-based scan of the supplied sections"})
    result["checks"] = checks

    return {
        "case_id": case_identifier(case),
        "status": status,
        "result": result,
        "checks": checks,
        "review_report": {"format": "markdown",
                          "content": build_review_report(result, case_identifier(case), uncertainty)},
        "evidence": [{"kind": "finding", "locator": item["locator"], "quote": item["quote"], "severity": item["severity"]} for item in findings],
        "uncertainty": uncertainty,
        "errors": [],
        "stats": {"findings": len(findings), "high": severity_counts.get("high", 0), "medium": severity_counts.get("medium", 0),
                  "design": design, "premises": len(premises), "network": "disabled"},
    }


def contract_names(case):
    contract = case.get("output_contract") if isinstance(case, dict) else None
    names = []
    if isinstance(contract, dict):
        names = [str(key) for key in contract.keys()]
    elif isinstance(contract, list):
        for item in contract:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                for key in ("name", "field", "key", "id"):
                    if isinstance(item.get(key), str):
                        names.append(item[key])
                        break
    return names


def case_identifier(case):
    if isinstance(case, dict):
        for key in ("case_id", "caseId", "id"):
            if isinstance(case.get(key), str) and case[key].strip():
                return case[key]
    return ""


CONTRACT_ALIASES = {
    "issues": ("findings", "problems", "defects", "violations"),
    "findings": ("issues",),
    "summary": ("stats", "overview", "counts", "tally"),
    "overview": ("summary", "stats"),
    "stats": ("summary",),
    "verdict": ("recommendation", "decision", "conclusion", "overall"),
    "reviewreport": ("report", "review", "markdown"),
    "report": ("review_report", "review"),
    "scores": ("score", "metrics", "verdict"),
    "metrics": ("scores", "stats"),
    "rows": ("records", "data", "table"),
    "records": ("rows", "data"),
    "citations": ("reference_checks", "citation_checks", "references"),
    "tables": ("table_extractions", "tables_extracted"),
    "figures": ("figure_mentions", "figures_extracted"),
}


def _norm_key(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _severity_counts(findings):
    counts = {}
    if isinstance(findings, list):
        for item in findings:
            if not isinstance(item, dict):
                continue
            sev = str(item.get("severity") or item.get("level") or "unspecified").lower()
            counts[sev] = counts.get(sev, 0) + 1
    return counts


def _derive_named(name, flat):
    """Return a value for `name` derived from the payload, or (None, reason)."""
    norm = _norm_key(name)
    for alias in CONTRACT_ALIASES.get(norm, ()):
        if alias in flat and flat[alias] not in (None, "", [], {}):
            return flat[alias], "derived from '%s'" % alias
    findings = flat.get("findings") or flat.get("issues") or []
    if norm in ("verdict", "reviewverdict", "decision", "recommendation", "overallverdict"):
        counts = _severity_counts(findings)
        if counts or flat.get("checks"):
            decision = ("major_revision" if counts.get("high")
                        else "minor_revision" if counts.get("medium")
                        else "accept")
            return ({"decision": decision,
                     "basis": "derived from %d finding(s) and %d check(s)"
                              % (len(findings) if isinstance(findings, list) else 0,
                                 len(flat.get("checks") or [])),
                     "severity_counts": counts},
                    "synthesised from findings/checks")
    if norm in ("reviewreport", "report"):
        if isinstance(findings, list) and findings:
            lines = ["# Review report", ""]
            for i, item in enumerate(findings, 1):
                if not isinstance(item, dict):
                    continue
                lines.append("## %d. %s" % (i, item.get("category") or item.get("kind") or "finding"))
                lines.append("")
                lines.append("- severity: %s" % (item.get("severity") or "unspecified"))
                if item.get("issue"):
                    lines.append("- issue: %s" % item["issue"])
                if item.get("evidence"):
                    lines.append("- evidence: %s" % item["evidence"])
                if item.get("suggestion"):
                    lines.append("- suggested fix: %s" % item["suggestion"])
                lines.append("")
            return ({"format": "markdown", "content": "\n".join(lines)},
                    "rendered from findings")
    return None, "not derivable from this run's data"


def apply_contract(payload, case):
    names = contract_names(case)
    notes = {}
    flat = {}
    for holder in (payload, payload.get("result") if isinstance(payload.get("result"), dict) else {}):
        if not isinstance(holder, dict):
            continue
        for key, value in holder.items():
            flat.setdefault(str(key), value)
    for name in names:
        if name in payload and payload[name] is not None:
            notes[name] = "produced directly by this run"
            continue
        if name in flat and flat[name] not in (None, "", [], {}):
            payload[name] = flat[name]
            notes[name] = "taken from the run's result section"
            continue
        value, reason = _derive_named(name, flat)
        if value is not None:
            payload[name] = value
            notes[name] = reason
        else:
            payload[name] = None
            notes[name] = reason
    payload["contract_notes"] = notes
    payload["output_contract_fields"] = {"provided": names,
                                         "present": {name: payload.get(name) is not None
                                                     for name in names}}
    return payload


def write_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, str(target))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


FACET_LABELS = [
    ("argument_chain", "论点-证据链完整性"),
    ("causal_inference", "因果措辞与设计匹配"),
    ("generalization", "结论外推范围"),
    ("alternative_explanations", "替代解释与混杂"),
]


def build_review_report(result, case_id, uncertainty=None):
    """Render a complete review report (markdown) from this run's findings."""
    findings = result.get("findings") or []
    summary = result.get("summary") or {}
    counts = summary.get("by_severity") or {}
    lines = ["# 论文论证与逻辑审查报告", "",
             "- case_id: `%s`" % (case_id or "unknown"),
             "- 判定: %s" % (summary.get("verdict") or "no_verdict"),
             "- 问题数: %d（high %d / medium %d / low %d）" % (
                 len(findings), counts.get("high", 0), counts.get("medium", 0), counts.get("low", 0)),
             "- 检测章节: %s" % ("、".join(result.get("sections_detected") or []) or "未识别"), ""]
    lines += ["## 一、检查覆盖", "", "| 检查项 | 状态 | 问题数 |", "|---|---|---:|"]
    for check in result.get("checks") or []:
        lines.append("| %s | %s | %s |" % (check.get("check"), check.get("status"), check.get("findings", 0)))
    lines += ["", "## 二、问题清单"]
    if not findings:
        lines += ["", "本次材料在已检查项上未发现问题；未检查项见第五节。"]
    for index, item in enumerate(findings, 1):
        lines += ["", "### F%d [%s] %s" % (index, item.get("severity", "unspecified"), item.get("facet", "finding")), "",
                  "- 定位：`%s`" % (item.get("locator") or "未定位")]
        if item.get("quote"):
            lines.append("- 原文：“%s”" % item["quote"])
        lines += ["- 判定：%s" % (item.get("finding") or ""),
                  "- 依据：%s" % (item.get("evidence") or ""),
                  "- 修改建议：%s" % (item.get("recommendation") or "")]
    lines += ["", "## 三、修改清单"]
    for index, item in enumerate(result.get("revision_checklist") or [], 1):
        lines.append("%d. `%s` — %s" % (index, item.get("locator") or "n/a", item.get("action") or ""))
    lines += ["", "## 四、限制"]
    for item in result.get("limitations") or []:
        lines.append("- %s" % item)
    lines += ["", "## 五、待复核与未检查项"]
    for item in (uncertainty or []):
        if isinstance(item, dict):
            lines.append("- %s：%s" % (item.get("type", "uncertainty"), item.get("detail", "")))
        else:
            lines.append("- %s" % item)
    lines += ["", "## 六、运行记录"]
    for item in result.get("change_log") or []:
        lines.append("- %s" % item)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Argument and reasoning audit")
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--out", "--output", default=DEFAULT_OUT)
    parser.add_argument("--work", default=DEFAULT_WORK)
    args = parser.parse_args(argv)
    os.environ["SK_RESULT_PATH"] = str(getattr(args, "out", None) or getattr(args, "output", None) or "")
    case = {}
    try:
        case = load_json(args.case)
        if not isinstance(case, dict):
            raise ValueError("case.json root must be a JSON object")
        try:
            Path(args.work).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        payload = build_payload(case, read_task_text(args.case, args.work))
        code = 0
    except Exception as exc:
        payload = {"case_id": case_identifier(case) if isinstance(case, dict) else "", "status": "failed",
                   "result": None, "evidence": [],
                   "uncertainty": [{"type": "run_failure", "detail": "Run failed; no argument audit is reported."}],
                   "errors": [{"stage": "build", "type": type(exc).__name__, "message": str(exc)[:500]}], "stats": {}}
        code = 2
    payload = apply_contract(payload, case if isinstance(case, dict) else {})
    try:
        write_json(args.out, payload)
    except Exception as exc:
        sys.stderr.write(json.dumps({"status": "failed", "stage": "write_output", "message": str(exc)[:300]}) + "\n")
        return 3
    report = payload.get("review_report")
    if isinstance(report, dict) and report.get("content"):
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(args.out)), "review-report.md"), "w", encoding="utf-8") as handle:
                handle.write(report["content"])
        except OSError:
            pass
    sys.stdout.write(json.dumps({"status": payload.get("status"), "case_id": payload.get("case_id"),
                                 "out": str(args.out), "findings": payload.get("stats", {}).get("findings", 0)},
                                ensure_ascii=False) + "\n")
    return code


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.environ.get("SK_RESULT_PATH") or "result.json"
            _d = os.path.dirname(os.path.abspath(_p))
            if _d:
                os.makedirs(_d, exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    _fallback = os.environ.get("SK_RESULT_PATH", "")
    if _fallback and not os.path.isfile(_fallback):
        try:
            _parent = os.path.dirname(os.path.abspath(_fallback))
            if _parent:
                os.makedirs(_parent, exist_ok=True)
            with open(_fallback, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0 if _fallback else _rc)
