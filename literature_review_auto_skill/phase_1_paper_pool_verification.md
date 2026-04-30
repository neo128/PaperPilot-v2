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

