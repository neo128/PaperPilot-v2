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

