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
