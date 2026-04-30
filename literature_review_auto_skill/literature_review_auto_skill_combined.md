# 系统性文献调研与综述自动化 Skill Pack（合并版）



---

# File: SKILL.md

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



---

# File: phase_1_paper_pool_verification.md

# Phase 1 Skill: 论文池复核与可靠资料基础建立

## 1. 阶段目标

将初始检索到的论文列表转化为可用于系统综述的可靠论文池。

本阶段只做：

- 检索；
- 去重；
- 元数据校验；
- 链接替换；
- 弱相关降级；
- 重要遗漏补齐；
- 来源质量标注。

本阶段不做正式综述写作，不做 A 层精读。

---

## 2. 输入

```yaml
topic: 研究主题
research_plan: 阶段 0 的研究计划
seed_papers: 用户提供的论文、PDF、链接或表格
target_venues: 目标会议/期刊
time_range: 时间范围
target_pool_size: 目标论文池规模
```

---

## 3. 检索策略

### 3.1 分组检索

针对任意主题，应使用多组关键词，而不是单一关键词。

模板：

```text
"{topic core term}" AND "{method term}"
"{topic core term}" AND "{task term}"
"{topic core term}" AND "{system term}"
"{topic core term}" AND benchmark
"{topic core term}" AND survey
"{topic core term}" AND dataset
```

### 3.2 来源优先级

优先检索：

1. 目标会议 / 期刊官网；
2. OpenReview；
3. CVF Open Access；
4. PMLR；
5. IEEE Xplore；
6. ACM Digital Library；
7. arXiv；
8. 项目主页；
9. GitHub；
10. Semantic Scholar / Google Scholar。

---

## 4. 复核字段

`paper_pool_verified.csv` 至少包含：

```csv
paper_id,title,year,authors,venue,venue_type,paper_url,official_url,arxiv_url,project_url,code_url,dataset_url,source_quality,verification_status,topic_relevance,reason_to_include,reason_to_exclude_or_downgrade,notes
```

字段说明：

| 字段 | 说明 |
|---|---|
| `paper_id` | 稳定编号，例如 P001 |
| `title` | 标题，必须核对准确 |
| `year` | 年份，优先使用正式出版年份 |
| `venue` | 会议/期刊/arXiv/workshop |
| `venue_type` | main_conference, journal, workshop, arxiv, preprint |
| `paper_url` | 最可靠的论文入口 |
| `official_url` | 官方页面 |
| `arxiv_url` | arXiv 页面 |
| `project_url` | 项目主页 |
| `code_url` | 代码仓库 |
| `source_quality` | official, primary, secondary, weak |
| `verification_status` | verified, partially_verified, needs_verification |
| `topic_relevance` | high, medium, low |
| `reason_to_include` | 纳入理由 |
| `reason_to_exclude_or_downgrade` | 降级或排除理由 |
| `notes` | 备注 |

---

## 5. 去重规则

如果出现以下情况，视为同一论文：

- arXiv 与会议正式版重复；
- 项目主页与论文主页重复；
- workshop 早期版与主会扩展版重复；
- 标题微调但作者和内容基本一致。

保留优先级：

```text
正式会议/期刊版本
> OpenReview/CVF/PMLR/IEEE 官方入口
> arXiv
> 项目主页
> GitHub
> Google Scholar / Semantic Scholar
```

---

## 6. 补齐规则

如果用户指定目标会议，应检查是否遗漏该会议中的代表性论文。

例如 AI / Robotics 主题常需要补齐：

```text
NeurIPS, ICLR, ICML, CVPR, ICCV, ECCV,
RSS, CoRL, ICRA, IROS, RAL,
ACL, EMNLP, NAACL,
SIGGRAPH, UIST, CHI,
OSDI, SOSP, NSDI, SIGMOD, VLDB
```

---

## 7. 输出

1. `paper_pool_raw.csv`
2. `paper_pool_verified.csv`
3. `paper_pool_verification_report.md`

`paper_pool_verification_report.md` 包含：

```markdown
# Paper Pool Verification Report

## Topic
## Input Sources
## Search Queries
## Source Coverage
## Venue Coverage
## Year Coverage
## Total Papers
## Added Papers
## Removed / Downgraded Papers
## Remaining Unverified Items
## Risks
## Next Step
```

---

## 8. 质量门槛

进入下一阶段前，必须满足：

```text
[ ] 每篇论文有标题、年份、来源
[ ] A/B 候选论文有可靠链接
[ ] 重复条目已合并
[ ] 弱相关条目被降级或剔除
[ ] 目标会议覆盖已检查
[ ] 未确认项已标注 needs_verification
[ ] 输出 paper_pool_verified.csv
```



---

# File: phase_2_unified_coding.md

# Phase 2 Skill: 统一编码与论文池结构化

## 1. 阶段目标

将 `paper_pool_verified.csv` 转换成可分析、可筛选、可横向比较的结构化数据集。

本阶段只做编码，不做 A 层精读，不写正式综述。

---

## 2. 输入

- `paper_pool_verified.csv`
- `research_plan.md`
- 用户指定的特殊关注维度

---

## 3. 输出

- `paper_pool_coded.csv`
- `coding_schema.md`
- `unified_coding_report.md`

---

## 4. 通用编码字段

`paper_pool_coded.csv` 应包含以下字段：

```csv
paper_id,title,year,venue,
tier,
research_direction,
task_type,
method_type,
model_or_system_type,
data_type,
benchmark_or_environment,
real_world_or_simulation,
open_source_status,
core_contribution,
main_limitation,
evidence_strength,
engineering_reusability,
relation_to_target_topic,
coding_confidence,
coding_note
```

---

## 5. 可扩展主题字段

根据主题增加专用字段。

### 5.1 具身智能 / 机器人主题

```csv
embodiment_level,
real_robot,
long_horizon_focus,
open_world_or_open_vocab_focus,
spatio_temporal_focus,
failure_recovery_mechanism,
update_mechanism,
forgetting_or_compression_mechanism
```

### 5.2 记忆 / Agent 主题

```csv
memory_type,
memory_carrier,
memory_lifecycle_stage,
write_mechanism,
retrieve_mechanism,
update_mechanism,
forgetting_mechanism,
reflection_mechanism,
memory_risk
```

### 5.3 世界模型主题

```csv
world_model_type,
temporal_modeling,
spatial_representation,
decision_coupling,
latent_or_pixel,
rollout_type,
training_objective,
planning_usage
```

### 5.4 数据集 / 数据质量主题

```csv
data_modality,
annotation_type,
quality_metric,
cleaning_method,
human_in_loop,
automated_qc,
evaluation_protocol
```

---

## 6. 分层规则

| Tier | 含义 | 标准 |
|---|---|---|
| A1 | 核心精读论文 | 高相关、高影响、有方法贡献或系统价值 |
| A2 | 核心候选 | 高相关但证据/影响/落地性略弱 |
| B | 支撑论文 | 用于横向对比、背景补充 |
| C | 背景论文 | 低相关或仅用于历史脉络 |

推荐 A1 数量：20—30 篇。  
推荐 A1 + A2 数量：50—70 篇。  
推荐总池：80—150 篇。

---

## 7. 编码置信度

| 置信度 | 含义 |
|---|---|
| high | 论文内容、来源、方法和结果均已可靠确认 |
| medium | 论文可靠，但某些字段需进一步细读 |
| low | 来源或相关性存在不确定性 |

---

## 8. 编码原则

- 宁可标注 `unclear`，不要猜测；
- 同一字段使用固定枚举，避免同义词混乱；
- 同一篇论文可以有多个标签，但主标签必须明确；
- `core_contribution` 和 `main_limitation` 都必须填写；
- 工程复用性应区分 `direct`, `adaptable`, `conceptual`, `low`。

---

## 9. 报告模板

`unified_coding_report.md`：

```markdown
# Unified Coding Report

## Input
## Output
## Added Fields
## Tier Distribution
## Direction Distribution
## Task Distribution
## Method Distribution
## Evidence Strength Distribution
## Low-confidence Items
## Coding Risks
## Recommended A1 Papers
## Next Step
```

---

## 10. 质量门槛

```text
[ ] 所有论文均有 tier
[ ] 所有论文均有 research_direction
[ ] 所有论文均有 method_type
[ ] 所有论文均有 contribution 和 limitation
[ ] A1 数量适合后续精读
[ ] 低置信度条目被标记
[ ] 输出 paper_pool_coded.csv
```



---

# File: phase_3_a_tier_reading.md

# Phase 3 Skill: A 层核心论文精读与证据卡片生成

## 1. 阶段目标

从 `paper_pool_coded.csv` 中选择 20—25 篇 A 层核心论文，形成一页式证据卡片，为正式综述提供高质量证据基础。

本阶段不做横向矩阵，不写综述定稿。

---

## 2. 输入

- `paper_pool_coded.csv`
- `paper_pool_verified.csv`
- 论文 PDF / 官方页面 / 项目页面
- 阶段 0 的研究问题

---

## 3. 选文标准

优先选择：

```text
[ ] 与主题高度相关
[ ] 提出关键概念或代表性方法
[ ] 在目标领域影响较大
[ ] 有明确实验或系统验证
[ ] 有真实系统 / benchmark / 数据集 / 代码之一
[ ] 能覆盖一个关键子方向
[ ] 对目标项目有借鉴价值
```

避免 A 层过度集中于单一会议或单一技术路线。

---

## 4. 一页式证据卡片模板

每篇论文使用以下模板：

```markdown
## Pxxx. Paper Title

**Year / Venue**:  
**Authors / Institution**:  
**Research Direction**:  
**Task Scenario**:  
**Problem**:  

### Method
- Core idea:
- Architecture / pipeline:
- Key mechanism:

### Experiments
- Dataset / benchmark:
- Real robot or simulation:
- Metrics:
- Main results:

### Contribution
1.
2.
3.

### Limitation
1.
2.
3.

### Relation to Current Review
- Why this paper matters:
- Which research question it supports:

### Engineering Reusability
- Directly reusable:
- Requires adaptation:
- Not suitable for direct reuse:

### Evidence
- Paper:
- Project:
- Code:
- Data:
```

---

## 5. 输出文件

- `A_tier_reading_notes.md`
- `A_tier_reading_notes.docx`，如需要
- `A_tier_reading_notes.pdf`，如需要
- `A_tier_reading_notes_index.csv`
- `a_tier_reading_report.md`

---

## 6. 索引表字段

`A_tier_reading_notes_index.csv`：

```csv
paper_id,title,year,venue,research_direction,task_type,method_type,key_contribution,key_limitation,review_section,evidence_url,code_url,reusability
```

---

## 7. 精读质量要求

每篇卡片必须回答：

```text
它解决什么问题？
它为什么重要？
它的方法是什么？
它的实验在哪里做？
它的结果说明了什么？
它的局限是什么？
它与本主题有什么关系？
它对目标系统有什么可借鉴点？
```

---

## 8. 常见错误

- 只复制摘要，不拆方法；
- 只写贡献，不写局限；
- 只写论文内容，不写与本主题关系；
- 不区分仿真和真实系统；
- 不说明代码 / 数据状态；
- 不说明能否工程复用。

---

## 9. 阶段报告模板

```markdown
# A-tier Reading Report

## Input
## Selection Criteria
## Selected Papers
## Coverage by Direction
## Coverage by Venue
## Coverage by Task
## Key Evidence Themes
## Remaining Gaps
## Next Step
```

---

## 10. 质量门槛

```text
[ ] 精读 20—25 篇核心论文
[ ] 每篇有完整证据卡片
[ ] 每篇有贡献和局限
[ ] 每篇有与综述主题的关系
[ ] 每篇有工程复用判断
[ ] 输出 index.csv
```



---

# File: phase_4_comparison_matrices.md

# Phase 4 Skill: 横向矩阵分析

## 1. 阶段目标

将论文池编码和 A 层精读卡片转化为横向比较矩阵，为综述中的分类框架、对比分析和挑战总结提供结构化依据。

本阶段不写正式综述定稿。

---

## 2. 输入

- `paper_pool_coded.csv`
- `A_tier_reading_notes.md`
- `A_tier_reading_notes_index.csv`
- `research_plan.md`

---

## 3. 输出

- `comparison_matrices.xlsx`
- `comparison_matrices_report.md`

---

## 4. 推荐工作表结构

`comparison_matrices.xlsx` 应至少包含：

```text
00_总览
01_方向x任务
02_方法优缺点
03_生命周期机制
04_Benchmark评估
05_工程落地性
06_A层证据索引
07_数据源_编码池
```

---

## 5. 矩阵 1：方向 × 任务

目的：识别哪些研究方向解决哪些任务，以及任务覆盖空白。

字段示例：

```csv
research_direction,task_type,representative_papers,main_methods,key_findings,gaps
```

---

## 6. 矩阵 2：方法载体 × 优缺点

目的：比较不同方法路线的适用场景、优势、局限。

字段示例：

```csv
method_type,representative_papers,strengths,limitations,best_fit_tasks,engineering_cost,risk
```

---

## 7. 矩阵 3：生命周期机制

适用于系统、Agent、记忆、数据闭环等主题。

字段示例：

```csv
lifecycle_stage,mechanism,representative_papers,input,output,update_rule,failure_mode,open_problem
```

典型生命周期：

```text
observe
write
store
index
retrieve
reason
act
evaluate
update
forget
recover
```

---

## 8. 矩阵 4：Benchmark / 评估

目的：识别现有实验环境和评估指标是否足以支撑结论。

字段示例：

```csv
benchmark_or_environment,papers,task_type,simulation_or_real,metrics,strengths,limitations,reproducibility
```

---

## 9. 矩阵 5：工程落地性

目的：判断哪些论文方法可以转化为实际系统模块。

字段示例：

```csv
paper_id,title,module_mapping,reusability_level,required_adaptation,dependencies,risks,fit_to_target_system
```

`reusability_level` 推荐枚举：

```text
direct
adaptable
conceptual
low
unknown
```

---

## 10. 报告模板

`comparison_matrices_report.md`：

```markdown
# Comparison Matrices Report

## Input Files
## Generated Sheets
## Key Patterns
## Evidence-backed Findings
## Method Comparison Summary
## Benchmark Gaps
## Engineering Reusability Findings
## Risks
## Next Step
```

---

## 11. 质量门槛

```text
[ ] 至少 5 张核心矩阵
[ ] 每张矩阵有代表论文
[ ] 每张矩阵有发现与缺口
[ ] 工程落地性不只给结论，还说明依赖和风险
[ ] 输出 xlsx 和报告
```



---

# File: phase_5_review_writing.md

# Phase 5 Skill: 文献综述定稿生成

## 1. 阶段目标

基于前面所有中间产物，生成可交付的正式文献综述。

输入证据必须来自：

- `paper_pool_verified.csv`
- `paper_pool_coded.csv`
- `A_tier_reading_notes`
- `comparison_matrices.xlsx`

禁止脱离证据直接写宏大观点。

---

## 2. 输入

```text
research_plan.md
paper_pool_verified.csv
paper_pool_coded.csv
A_tier_reading_notes.md/docx
A_tier_reading_notes_index.csv
comparison_matrices.xlsx
comparison_matrices_report.md
```

---

## 3. 输出

```text
review_v1.md
review_v1.docx
review_v1.pdf
review_generation_report.md
```

可选：

```text
references.bib
figures/
appendix_tables.xlsx
```

---

## 4. 推荐综述结构

```markdown
# Title

## 摘要
## 关键词

## 1. 引言
- 研究背景
- 为什么该主题重要
- 现有综述不足
- 本文贡献

## 2. 检索与筛选方法
- 时间范围
- 检索来源
- 关键词
- 纳入 / 排除标准
- 论文池统计

## 3. 概念界定与分类框架
- 核心术语
- 分类维度
- 分类框架图 / 表

## 4. 主题主线一
## 5. 主题主线二
## 6. 主题主线三
## 7. 主题主线四

## 8. 横向比较
- 方法比较
- 数据集 / Benchmark 比较
- 评估指标比较
- 工程落地性比较

## 9. 关键挑战
- 数据挑战
- 模型挑战
- 系统挑战
- 评估挑战
- 工程部署挑战

## 10. 未来方向
- 短期可推进
- 中期关键突破
- 长期开放问题

## 11. 对目标系统 / 项目的启示
- 可复用模块
- 需改造模块
- 不建议直接采用的路线
- 推荐技术路线

## 12. 结论

## 参考文献
```

---

## 5. 写作规则

### 5.1 证据优先

每一节至少对应：

- A 层证据卡片；
- 或横向矩阵；
- 或 verified paper pool 中的可靠来源。

### 5.2 不确定性表达

对以下情况必须谨慎表达：

```text
arXiv only
workshop only
no real robot validation
simulation only
no code
unclear benchmark
small-scale experiment
not independently reproduced
```

### 5.3 不写无证据判断

避免：

```text
这是未来唯一方向
该方法已经完全解决问题
该系统可直接工业部署
所有研究都表明
```

推荐：

```text
现有证据更支持……
在已检索论文中……
在仿真环境下表现出……
真实部署仍需要……
```

---

## 6. 参考文献格式

根据用户要求选择：

- GB/T 7714；
- APA；
- IEEE；
- ACM；
- BibTeX。

如果用户未指定，中文综述建议使用 GB/T 7714，英文综述建议使用 IEEE 或 APA。

---

## 7. 图表建议

至少包含：

```text
论文池筛选流程图
年份分布图
会议/来源分布图
分类框架图
方法对比表
Benchmark 对比表
工程落地性表
未来研究路线图
```

---

## 8. 生成报告模板

`review_generation_report.md`：

```markdown
# Review Generation Report

## Input Artifacts
## Review Version
## Section Mapping
## Evidence Mapping
## Citation Status
## Known Limitations
## Suggested Next Revision
```

---

## 9. 质量门槛

```text
[ ] 综述引用来源可追溯
[ ] 综述结构完整
[ ] 有检索方法说明
[ ] 有分类框架
[ ] 有横向对比
[ ] 有挑战和未来方向
[ ] 有对目标项目的启示
[ ] 有局限性说明
[ ] 输出 docx/pdf/md
```



---

# File: schemas_and_templates.md

# Schemas and Templates for Literature Review Automation

## 1. `research_plan.md` 模板

```markdown
# Research Plan: {topic}

## 1. Topic
## 2. Scope
## 3. Research Questions
### RQ1
### RQ2
### RQ3
## 4. Time Range
## 5. Target Venues / Sources
## 6. Inclusion Criteria
## 7. Exclusion Criteria
## 8. Search Query Groups
## 9. Expected Deliverables
## 10. Risks and Assumptions
```

---

## 2. `paper_pool_verified.csv` Schema

```csv
paper_id,title,year,authors,venue,venue_type,paper_url,official_url,arxiv_url,project_url,code_url,dataset_url,source_quality,verification_status,topic_relevance,reason_to_include,reason_to_exclude_or_downgrade,notes
```

---

## 3. `paper_pool_coded.csv` Schema

```csv
paper_id,title,year,venue,tier,research_direction,task_type,method_type,model_or_system_type,data_type,benchmark_or_environment,real_world_or_simulation,open_source_status,core_contribution,main_limitation,evidence_strength,engineering_reusability,relation_to_target_topic,coding_confidence,coding_note
```

---

## 4. A 层证据卡片模板

```markdown
## {paper_id}. {title}

**Year / Venue**:  
**Authors / Institution**:  
**Research Direction**:  
**Task Scenario**:  
**Problem**:  

### Method
- Core idea:
- Architecture / pipeline:
- Key mechanism:

### Experiments
- Dataset / benchmark:
- Real robot or simulation:
- Metrics:
- Main results:

### Contribution
1.
2.
3.

### Limitation
1.
2.
3.

### Relation to Current Review
- Why this paper matters:
- Which research question it supports:

### Engineering Reusability
- Directly reusable:
- Requires adaptation:
- Not suitable for direct reuse:

### Evidence
- Paper:
- Project:
- Code:
- Data:
```

---

## 5. `A_tier_reading_notes_index.csv` Schema

```csv
paper_id,title,year,venue,research_direction,task_type,method_type,key_contribution,key_limitation,review_section,evidence_url,code_url,reusability
```

---

## 6. `comparison_matrices.xlsx` Workbook

Sheets:

```text
00_总览
01_方向x任务
02_方法优缺点
03_生命周期机制
04_Benchmark评估
05_工程落地性
06_A层证据索引
07_数据源_编码池
```

### Sheet: `01_方向x任务`

```csv
research_direction,task_type,representative_papers,main_methods,key_findings,gaps
```

### Sheet: `02_方法优缺点`

```csv
method_type,representative_papers,strengths,limitations,best_fit_tasks,engineering_cost,risk
```

### Sheet: `03_生命周期机制`

```csv
lifecycle_stage,mechanism,representative_papers,input,output,update_rule,failure_mode,open_problem
```

### Sheet: `04_Benchmark评估`

```csv
benchmark_or_environment,papers,task_type,simulation_or_real,metrics,strengths,limitations,reproducibility
```

### Sheet: `05_工程落地性`

```csv
paper_id,title,module_mapping,reusability_level,required_adaptation,dependencies,risks,fit_to_target_system
```

---

## 7. `review_v1.md` Template

```markdown
# {Review Title}

## 摘要
## 关键词

## 1. 引言
## 2. 检索与筛选方法
## 3. 概念界定与分类框架
## 4. 主题主线一
## 5. 主题主线二
## 6. 主题主线三
## 7. 主题主线四
## 8. 横向比较
## 9. 关键挑战
## 10. 未来方向
## 11. 对目标系统 / 项目的启示
## 12. 结论
## 参考文献
```


---

# File: prompt_templates.md

# Prompt Templates for Literature Review Automation

## 1. 启动研究任务

```text
我要针对【主题名称】做系统性文献调研和综述。

目标：
1. 检索近【N】年代表性论文；
2. 覆盖【目标会议/期刊】；
3. 建立约【数量】篇论文池；
4. 标注每篇论文的方向、方法、贡献、局限；
5. 输出带引用的文献综述初稿。

要求：
这一阶段不要急着写大观点，重点是把资料找全、证据坐实。
请先给出研究问题、检索策略、纳入/排除标准、论文池字段设计和阶段性交付计划。
```

---

## 2. 执行第 1 阶段：论文池复核

```text
请按研究计划执行第 1 阶段：论文池复核。

任务：
1. 建立或读取初始论文池；
2. 校验标题、年份、会议、官方链接；
3. 合并重复条目；
4. 删除或降级弱相关论文；
5. 补齐遗漏的重要论文，尤其是【指定会议/方向】；
6. 输出 paper_pool_verified.csv 和 paper_pool_verification_report.md。

注意：
只做复核，不进入统一编码和综述写作。
```

---

## 3. 执行第 2 阶段：统一编码

```text
请基于 paper_pool_verified.csv 执行第 2 阶段：统一编码。

新增字段：
research_direction
task_type
method_type
model_or_system_type
data_type
benchmark_or_environment
real_world_or_simulation
core_contribution
main_limitation
evidence_strength
engineering_reusability
relation_to_target_topic
tier
coding_confidence

如果主题需要，请补充专用字段。

输出：
paper_pool_coded.csv
coding_schema.md
unified_coding_report.md。

注意：
只做统一编码，不进入核心论文精读。
```

---

## 4. 执行第 3 阶段：A 层精读

```text
请从 paper_pool_coded.csv 中选择 20—25 篇 A 层核心论文进行精读。

每篇形成一页式证据卡片，包括：
论文标题
年份 / 会议
研究问题
方法概述
系统结构
实验设置
主要结果
核心贡献
主要局限
与本主题的关系
可借鉴点
不适合直接借鉴点
证据来源
代码 / 数据状态

输出：
A_tier_reading_notes.docx
A_tier_reading_notes.md
A_tier_reading_notes_index.csv。
```

---

## 5. 执行第 4 阶段：横向矩阵

```text
请基于 paper_pool_coded.csv 和 A_tier_reading_notes 执行第 4 阶段：横向矩阵分析。

至少包括：
1. 方向 × 任务矩阵；
2. 方法载体 × 优缺点矩阵；
3. 生命周期 / 流程机制矩阵；
4. Benchmark / 评估指标矩阵；
5. 工程落地性矩阵。

输出：
comparison_matrices.xlsx
comparison_matrices_report.md。

注意：
只做矩阵分析，不进入综述定稿。
```

---

## 6. 执行第 5 阶段：综述定稿

```text
请基于以下材料完成正式文献综述：
1. paper_pool_verified.csv
2. paper_pool_coded.csv
3. A_tier_reading_notes
4. comparison_matrices.xlsx

要求：
1. 保留可追溯引用；
2. 不写无证据支撑的大判断；
3. 结构包括引言、概念界定、检索方法、分类框架、主题综述、横向比较、挑战、未来方向、对目标系统的启示；
4. 输出 review_v1.docx、review_v1.pdf 和 review_generation_report.md。
```

---

## 7. 全流程自动执行

```text
请对【主题名称】执行完整的系统性文献调研与综述自动化流程。

模式：full_auto

要求依次完成：
0. research_plan.md
1. paper_pool_verified.csv
2. paper_pool_coded.csv
3. A_tier_reading_notes
4. comparison_matrices.xlsx
5. review_v1.docx / review_v1.pdf

要求：
- 每个阶段都要保留中间产物；
- 每个阶段都要有报告；
- 不确定项要标注；
- 不得跳过证据复核直接写综述；
- 最终回答列出所有文件链接和阶段统计。
```
