---
name: manuscript-argument-logic-audit
description: Use when a manuscript's reasoning must be audited, requiring reconstruction of the aim-to-conclusion chain, detection of causal wording under observational designs, scope overshoot, unanchored inference markers, missing alternative explanations, an explicit hypothesis verdict and located severity-rated findings.
---

# 论文逻辑与论证审查

## 用途与适用条件

当任务要求审查「论证是否走得通」而不是核对格式时使用：重建「目的 → 设计 → 证据 → 解释 → 结论」链条，检查结论是否回答目的、因果措辞是否有实验设计支撑、结论是否超出样本范围、因此/thus 类推断是否锚定到结果、观察性研究是否讨论替代解释。

**适用前提**：`case.json` 提供稿件正文或章节映射。至少要有结果与结论（或讨论）文本才能形成链条。

**不适用**：形式逻辑证明、统计重算、查重、替作者重写全文、判断研究价值。

## Quickstart

包内自带一个合成演示案例，可直接跑通：

```powershell
python scripts/run_skill.py --case examples/demo-case/case.json --out "$env:TEMP\demo_16d4414d\result.json" --work "$env:TEMP\demo_16d4414d\work"
```

- 演示输入：`examples/demo-case/case.json`，5 章节合成稿件（横断面设计，却在讨论中写 "therefore causes … in all adults"）。
- 输出：`$env:TEMP\demo_16d4414d\result.json`，`status=success`，4 条 findings（1 high / 3 medium），`verdict.decision=major_revision`。
- `output_contract` 的 `issues`、`summary`、`verdict` 三个键均非空；同一输入连续两次运行的 result.json 字节一致。

> 案例文本为合成内容，不代表任何真实论文或官方评测数据。

## 输入

| 输入 | 说明 |
|---|---|
| `/input/case.json` | `manuscript`/`paper`/`text`，整段文本或 `{Introduction, Methods, Results, Discussion, Conclusion}` 章节映射。 |
| `task.md` | 可选，无稿件字段时使用。 |
| `--work` | 默认 `/app/work`。 |

## 处理流程

1. **链条重建**（任务完成度）：定位目的、方法、结果、讨论、结论；提取含数值或比较词的结果句为前提；输出 `argument_map` 的节点与边，缺失边记为 gap。
2. **目的—结论对应**（正确性）：比较目的与结论的核心词项重叠，低于 0.15 提示结论未回答目的。
3. **因果推断**（正确性）：方法/全文识别实验或观察设计；观察性设计下出现 cause/leads to/导致 且无 hedge 时记 high；设计不明记 medium。
4. **范围外推**（正确性）：结论出现 all/every/普遍 等全称词，而方法限定在小鼠、细胞、单中心等范围时记 medium。
5. **推断锚定**（完整性）：therefore/thus/因此 句若无引用且无结果词项，记 medium 并列出未锚定推断。
6. **替代解释与假设裁决**（完整性）：观察性研究未讨论混杂/替代解释记 medium；目的为假设式而结论未给出支持/不支持裁决记 medium。

## 输出契约

顶层：`case_id`、`status`、`result`、`checks`、`review_report`、`evidence`、`uncertainty`、`errors`、`stats`、`contract_notes`、`output_contract_fields`。同时写出 `review-report.md`（可直接交付的论证审查报告）。

`result` 含：`sections_detected`、`argument_map`（aim/design/premises/inference_markers/conclusion/edges）、`findings`（facet/severity/locator/quote/finding/evidence/recommendation/status）、`gaps`、`summary`（total/by_severity/verdict）、`revision_checklist`、`limitations`、`change_log`。

输入 `output_contract` 的字段名全部保留；无法产出写 `null` 并在 `contract_notes` 说明。

`status`：无正文 → `insufficient_input`；缺结果或结论 → `partial`；齐备 → `success`；解析失败 → `failed`。

## 异常处理

| 情形 | 处理 | 标记 |
|---|---|---|
| 缺结果章节 | 记 high，结论无证据链接 | `gaps.type=missing_evidence_link` |
| 缺结论 | 用讨论代替并声明 | `uncertainty.type=no_conclusion` |
| 设计无法识别 | 因果检查保守处理 | `uncertainty.type=design_unclear` |
| 观察性设计因果措辞 | 记 high | `facet=causal_inference` |
| 全称结论 | 记 medium | `facet=generalization` |
| 推断句无锚点 | 记 medium | `facet=argument_chain` |
| 输出不可写 | stderr 错误，退出码 3 | 无静默成功 |

## 限制

- 论证链由章节文本重建，不是形式逻辑解析。
- 因果措辞按线索词识别；有充分设计的因果分析仍可能成立。
- 外推检查依赖显式范围词与全称词，隐含外推可能漏检。
- 不重算数据，前提本身的真假未验证。

## 最小调用示例（示例，非正式案例结果）

```bash
python /skills/weekly-skill/scripts/run_skill.py --case /input/case.json --out /app/output/result.json --work /app/work
```

```json
{"case_id":"demo-al-01","manuscript":{
 "Introduction":"This study aims to test whether coffee reduces stroke risk.",
 "Methods":"A cross-sectional survey of 400 adults measured coffee intake.",
 "Results":"Coffee intake was associated with lower stroke risk (OR 0.8).",
 "Discussion":"Coffee therefore causes a reduction in stroke risk in all adults.",
 "Conclusion":"Coffee reduces stroke risk."}}
```

示意输出（示例）：`{"status":"success","result":{"argument_map":{"design":{"type":"observational"}},"summary":{"by_severity":{"high":1,"medium":2}}}}`。不代表任何官方固定案例结果。


## 交付要求

- 运行：`python scripts/run_skill.py --case /input/case.json --out /app/output/result.json`（`--output` 等价）。
- 单次运行产出完整成品：`result.json`（契约字段齐全）与 `review-report.md`（可直接复核的报告，含结论、检查覆盖、问题清单、修改清单、限制）。
- 每个问题附定位、原文、判定、依据与修改建议；覆盖输入中的全部章节与条目，不静默跳过。
- 输入缺失、JSON 损坏或输出不可写时，仍写出结构化 `result.json` 并正常退出；未检查项写入 `uncertainty` / `limitations`，不伪造内容。
- 结果由输入驱动，保持确定性（同一输入双跑字节一致）；不联网、不声称平台评分。

## 输入发现与伴随产物

- 输入发现：除 `case.json` 字段外，运行时会扫描其所在目录的 `manuscript.md`、`paper.txt`、`*.json`、`*.jsonl`、`*.csv` 等真实文件并合并；按内容判断稿件/参考文献角色，文件名不作标签；发现清单写入 `provenance.json`。
- 伴随产物（单次运行同时写出）：`review.json`、`checklist.csv`、`report.md`、`provenance.json`、`validation.json`。`output_contract` 字段若对应这些产物，`result.json` 直接给出文件名并在 `contract_notes` 说明。
- `validation.json` 记录契约覆盖、计数对账与引文核验结果（`locator_status.n_locator_issues`）。
- 证据复核：`result.verification` 给出 `quotes_checked` / `quotes_verified` / `verification_rate`，每条引文附 `paragraph_id` 与 `quote_verified`（逐字比对真实材料）；未定位项进入 `human_confirm`，不静默放行。
