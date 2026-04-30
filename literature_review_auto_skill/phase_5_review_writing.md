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

