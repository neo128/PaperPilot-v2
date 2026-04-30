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
