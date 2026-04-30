# Literature Review Auto Skill Pack

这个目录是一套可复用的 AI 自动化 Skill 文档，用于围绕任意研究主题完成系统性文献调研和高质量综述生成。

## 文件说明

| 文件 | 用途 |
|---|---|
| `SKILL.md` | 主 Skill，总控流程 |
| `phase_1_paper_pool_verification.md` | 第 1 阶段：论文池复核 |
| `phase_2_unified_coding.md` | 第 2 阶段：统一编码 |
| `phase_3_a_tier_reading.md` | 第 3 阶段：A 层精读 |
| `phase_4_comparison_matrices.md` | 第 4 阶段：横向矩阵 |
| `phase_5_review_writing.md` | 第 5 阶段：综述定稿 |
| `schemas_and_templates.md` | CSV / Markdown / Workbook 模板 |
| `prompt_templates.md` | 可直接复用的提示词模板 |

## 推荐用法

1. 先把 `SKILL.md` 作为系统指令或 Agent Skill；
2. 根据执行阶段调用对应 phase 文档；
3. 使用 `schemas_and_templates.md` 固定输出字段；
4. 使用 `prompt_templates.md` 驱动 stepwise 或 full_auto 工作流。

## 核心流程

```text
research_plan.md
→ paper_pool_verified.csv
→ paper_pool_coded.csv
→ A_tier_reading_notes
→ comparison_matrices.xlsx
→ review_v1.docx/pdf
```
