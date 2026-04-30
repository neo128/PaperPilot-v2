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

