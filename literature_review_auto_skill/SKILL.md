# Skill: 系统性文献调研与高质量综述自动化

## 1. 技能定位

本 Skill 用于针对任意研究主题，自动化完成从“研究问题定义 → 文献检索 → 论文池复核 → 统一编码 → 核心论文精读 → 横向矩阵分析 → 综述定稿”的全流程。

适用主题包括但不限于：

- 具身智能、VLA、世界模型、机器人长期自主、语义地图、主动探索；
- 多智能体、LLM Agent、长时记忆、RAG、智能体操作系统；
- 机器人硬件、力控关节、触觉传感、遥操作、数据采集；
- 任意 AI / Robotics / ML / HCI / Systems 方向的系统性综述。

本 Skill 的核心目标不是快速生成一篇“像综述”的文章，而是建立一个**可追溯、可复核、可扩展、可复用**的研究资料资产。

---

## 2. 使用前提

执行前应尽量获得以下输入：

```yaml
topic: 研究主题
scope: 研究边界
time_range: 文献时间范围，例如近 5 年
target_venues: 目标会议/期刊/来源
paper_pool_size: 目标论文池规模，例如 80-150 篇
language: 输出语言
deliverables: 目标交付物，例如 csv/xlsx/docx/pdf/md
special_focus:
  - 是否关注真实系统
  - 是否关注工程落地
  - 是否关注开源代码
  - 是否关注 benchmark
  - 是否关注某一应用场景
mode: stepwise 或 full_auto
```

如果输入不完整，AI 应基于主题给出合理默认值，并显式记录假设。

---

## 3. 总体原则

### 3.1 先资料，后观点

禁止一开始直接写“大观点”“趋势判断”“技术路线结论”。必须先建立证据基础。

推荐顺序：

```text
研究任务定义
→ 初始论文池
→ 论文池复核
→ 统一编码
→ A 层论文精读
→ 横向矩阵分析
→ 综述定稿
```

### 3.2 先证据，后写作

每个关键判断都应追溯到论文或可靠来源。对不确定信息应标注：

- `needs_verification`
- `low_confidence`
- `arxiv_only`
- `workshop_only`
- `unclear_venue`
- `missing_code`
- `missing_benchmark`

### 3.3 分阶段交付

在 `stepwise` 模式下，每完成一个阶段就停下并报告，不越级进入下一阶段。  
在 `full_auto` 模式下，可以连续执行，但必须保留每个阶段的中间产物。

### 3.4 可复核优先

优先使用以下来源：

1. 会议 / 期刊官方页面；
2. OpenReview、CVF、PMLR、IEEE、ACM；
3. arXiv；
4. 项目主页；
5. GitHub；
6. 作者主页；
7. Semantic Scholar / Google Scholar；
8. 博客、媒体、二手文章。

综述正文中的引用应尽量来自 1—5 类来源。

---

## 4. 阶段总览

| 阶段 | 名称 | 目标 | 核心产物 |
|---|---|---|---|
| 0 | 研究任务定义 | 收敛主题和研究问题 | `research_plan.md` |
| 1 | 论文池复核 | 建立可靠论文池 | `paper_pool_verified.csv` |
| 2 | 统一编码 | 将论文池变成可分析数据集 | `paper_pool_coded.csv` |
| 3 | A 层精读 | 形成核心论文证据卡片 | `A_tier_reading_notes.md/docx` |
| 4 | 横向矩阵 | 形成比较分析骨架 | `comparison_matrices.xlsx` |
| 5 | 综述定稿 | 输出正式综述 | `review_v1.docx/pdf` |

---

## 5. 阶段 0：研究任务定义

### 5.1 目标

明确这次综述研究什么、不研究什么、如何评估资料是否相关。

### 5.2 操作

生成以下内容：

```markdown
# Research Plan

## Topic
## Research Scope
## Core Research Questions
## Sub-questions
## Time Range
## Target Venues / Sources
## Inclusion Criteria
## Exclusion Criteria
## Search Strategy
## Deliverables
## Risk Notes
```

### 5.3 输出

- `research_plan.md`

### 5.4 质量门槛

进入下一阶段前必须确认：

- 主题边界清楚；
- 至少有 3—6 个研究问题；
- 纳入 / 排除标准明确；
- 检索关键词分组明确；
- 目标会议 / 来源清楚。

---

## 6. 阶段 1：论文池复核

详见：`phase_1_paper_pool_verification.md`

### 6.1 输入

- 用户给出的种子论文、链接、PDF、已有 CSV；
- 阶段 0 的研究计划；
- 线上检索结果。

### 6.2 核心任务

1. 检索初始论文；
2. 合并重复条目；
3. 校验标题、年份、会议、链接；
4. 删除或降级弱相关条目；
5. 补齐遗漏的重要论文；
6. 标注来源质量和证据状态。

### 6.3 输出

- `paper_pool_raw.csv`
- `paper_pool_verified.csv`
- `paper_pool_verification_report.md`

---

## 7. 阶段 2：统一编码

详见：`phase_2_unified_coding.md`

### 7.1 核心任务

对 `paper_pool_verified.csv` 中每篇论文补全统一标签，包括：

- 研究方向；
- 任务类型；
- 方法类型；
- 系统形态；
- 数据 / benchmark；
- 真实系统程度；
- 贡献；
- 局限；
- 工程复用性；
- 与目标主题关系；
- A/B/C 分层；
- 编码置信度。

### 7.2 输出

- `paper_pool_coded.csv`
- `coding_schema.md`
- `unified_coding_report.md`

---

## 8. 阶段 3：A 层核心论文精读

详见：`phase_3_a_tier_reading.md`

### 8.1 核心任务

从 `paper_pool_coded.csv` 中选择 20—25 篇 A 层论文，每篇形成一页式证据卡片。

### 8.2 输出

- `A_tier_reading_notes.md`
- `A_tier_reading_notes.docx`
- `A_tier_reading_notes.pdf`
- `A_tier_reading_notes_index.csv`
- `a_tier_reading_report.md`

---

## 9. 阶段 4：横向矩阵分析

详见：`phase_4_comparison_matrices.md`

### 9.1 核心任务

基于编码池和精读卡片，形成横向对照表，包括：

1. 方向 × 任务；
2. 方法载体 × 优缺点；
3. 生命周期机制；
4. Benchmark / 评估指标；
5. 工程落地性；
6. A 层证据索引。

### 9.2 输出

- `comparison_matrices.xlsx`
- `comparison_matrices_report.md`

---

## 10. 阶段 5：综述定稿

详见：`phase_5_review_writing.md`

### 10.1 核心任务

基于全部中间产物生成正式综述，保留可追溯引用。

### 10.2 输出

- `review_v1.docx`
- `review_v1.pdf`
- `review_v1.md`
- `reference_list.bib`，可选
- `review_generation_report.md`

---

## 11. 文件命名规范

建议每个项目建立独立目录：

```text
literature_review_{topic_slug}/
  research_plan.md
  paper_pool_raw.csv
  paper_pool_verified.csv
  paper_pool_verification_report.md
  paper_pool_coded.csv
  coding_schema.md
  unified_coding_report.md
  A_tier_reading_notes.md
  A_tier_reading_notes.docx
  A_tier_reading_notes_index.csv
  comparison_matrices.xlsx
  comparison_matrices_report.md
  review_v1.md
  review_v1.docx
  review_v1.pdf
  references/
  source_pdfs/
```

---

## 12. 自动化执行协议

### 12.1 Stepwise 模式

每完成一个阶段，AI 必须输出：

```markdown
## 当前阶段完成情况
## 已生成文件
## 关键统计
## 发现的问题
## 下一阶段建议
```

并停止，等待用户说“继续”。

### 12.2 Full-auto 模式

如果用户明确要求“直接完成全流程”，AI 可以连续执行所有阶段，但必须：

- 保留每个中间文件；
- 在最终报告中列出阶段统计；
- 不用最终综述替代中间证据文件；
- 明确说明不确定项和未能验证项。

---

## 13. 质量检查清单

执行结束前检查：

```text
[ ] 是否有研究计划
[ ] 是否有 verified paper pool
[ ] 是否有 coded paper pool
[ ] 是否有 A 层精读卡片
[ ] 是否有横向矩阵
[ ] 是否有正式综述
[ ] 是否有每阶段报告
[ ] 是否标记了不确定条目
[ ] 是否避免无证据大判断
[ ] 是否保留可追溯引用
```

---

## 14. 禁止事项

- 不得凭记忆伪造论文、会议、链接或结果。
- 不得把 Google Scholar 页面当作最终官方引用。
- 不得将 arXiv 版本误写为已录用主会。
- 不得在论文池未复核前写正式综述。
- 不得只写贡献而不写局限。
- 不得把“有代码”写成“可复现”，除非已核验。
- 不得平均精读所有论文，应分层处理。
- 不得跳过 `paper_pool_coded.csv` 直接写综述。
- 不得在没有证据卡片的情况下提出强结论。

---

## 15. 最小可行流程

如果时间极短，至少执行：

```text
research_plan.md
→ paper_pool_verified.csv
→ paper_pool_coded.csv
→ 10 篇 A 层证据卡片
→ 3 张核心矩阵
→ review_brief.md
```

但必须标注为 `rapid_review`，不能声称是完整系统综述。

