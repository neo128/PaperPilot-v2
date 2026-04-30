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

