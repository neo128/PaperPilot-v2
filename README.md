# PaperPilot v2

PaperPilot v2 是对 PaperPilot 的重构版工程化实现，当前已经具备从论文发现、导入、总结到同步的端到端雏形。

## 当前能力

- `watch`，基于 DeepXiv 搜索论文并导入 Zotero
- `summary`，支持 Zotero / 本地 PDF，总结优先走 DeepXiv，失败回退 PDF
- `notion-sync`，把 Zotero 条目同步到 Notion database
- `pipeline`，统一 orchestrator 串联多 stage
- `sqlite state`，记录 run / stage / item state，支持基础增量处理
- 统一 clients / config / results / tests

## 目录结构

```text
paperpilot/
  cli/          # CLI 入口
  clients/      # 外部系统客户端封装
  models/       # 数据模型
  pipeline/     # pipeline config / orchestrator
  services/     # 业务服务层
  storage/      # SQLite 状态层
  utils/        # 配置、环境、HTTP 工具
tests/          # 测试
```

## 快速开始

```bash
cd ~/Code/PaperPilot-v2
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
```

DeepXiv 配置建议：

- `DEEPXIV_BASE_URL=https://data.rag.ac.cn`
- 不要在该值后面额外加 `/api`，否则 `search / brief / preview` 会命中错误路径

AI 配置建议写在本地 `.env`，不要提交真实 key：

```bash
AI_PROVIDER=openai
AI_BASE_URL=https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
AI_API_KEY=你的阿里云TokenPlanKey
AI_MODEL=你的模型名
```

## 统一 CLI

```bash
python -m paperpilot.cli.main run \
  --watch-query "agent memory" \
  --watch-dry-run \
  --summary-use-deepxiv \
  --notion-dry-run
```

也可以分别运行：

```bash
python -m paperpilot.cli.watch "agent memory" --dry-run
python -m paperpilot.cli.summary --tag AI
python -m paperpilot.cli.notion_sync --dry-run
python -m paperpilot.cli.pipeline --summary-use-deepxiv --notion-dry-run
```

## AI Summary 分层与 Zotero 附件

`summary` 支持本地 PDF 生成 canonical AI summary。默认写入 SQLite；使用 `--summary-dir` 时也会输出 Markdown 文件。

```bash
python -m paperpilot.cli.main summary \
  --pdf-path /path/to/paper.pdf \
  --summary-dir .paperpilot/test-summaries \
  --summary-db-path .paperpilot/summaries.sqlite3 \
  --max-pages 0 \
  --max-chars 200000 \
  --mode general \
  --force-summary \
  --no-zotero-attachment
```

如果已有本地 Markdown summary，并且有 `paper_id,zotero_key,title` 映射 CSV，可以批量挂到对应 Zotero 条目下。默认可先 dry-run：

```bash
python -m paperpilot.cli.main summary attach \
  --summary-dir .paperpilot/test-summaries/full-real-5 \
  --mapping-csv .review_projects/active-exploration-world-models/bib/citation_keys.csv \
  --dry-run
```

确认后去掉 `--dry-run` 即可上传 Markdown 附件。上传前会检查同名、同标题或 `AI总结-v2-md` 标签，避免重复挂载。

## Zotero 维护

清理旧的 Zotero rich-text AI note 时，使用 `zotero cleanup-ai-notes`。该命令默认 dry-run，并会先备份匹配 note HTML；只有加 `--apply` 才会删除。

```bash
python -m paperpilot.cli.main zotero cleanup-ai-notes \
  --after 2026-04-01

python -m paperpilot.cli.main zotero cleanup-ai-notes \
  --after 2026-04-01 \
  --apply
```

## 运行日志

通过 `paperpilot.cli.main` 运行的命令会写入：

- `.paperpilot/logs/*.log`
- `.paperpilot/logs/*.jsonl`

可通过环境变量调整：

```bash
PAPERPILOT_LOG_LEVEL=DEBUG
PAPERPILOT_LOG_CONSOLE_LEVEL=WARNING
PAPERPILOT_LOG_DIR=.paperpilot/logs
```

## 文献综述 Phase 1：检索并纳入 Zotero

`watch` 可作为系统性综述的第一步：根据主题或提示词检索论文，先在 Zotero 中按 DOI / arXiv ID / 标题查重；命中已有条目则直接复用，未命中才新增。

```bash
python -m paperpilot.cli.watch "agent memory" \
  --expand-queries \
  --prompt "long-term autonomous agent memory benchmark dataset survey" \
  --journals \
  --limit 30 \
  --collection-name "Review - Agent Memory" \
  --create-collections
```

如果只想预览候选数量和将要新增的条目：

```bash
python -m paperpilot.cli.watch "agent memory" --expand-queries --dry-run
```

## 文献综述自动化

`review` 是面向系统性综述的新入口，会在本地建立可复核的综述工作区，并把 Zotero 文献库作为文献管理中心。

```bash
python -m paperpilot.cli.main review init \
  --topic "agent memory" \
  --slug agent-memory

python -m paperpilot.cli.main review build-pool \
  --slug agent-memory \
  --topic "agent memory" \
  --collection-name "Review - Agent Memory" \
  --limit 100

python -m paperpilot.cli.main review read \
  --slug agent-memory \
  --topic "agent memory" \
  --limit 25 \
  --use-deepxiv

python -m paperpilot.cli.main review draft \
  --slug agent-memory \
  --topic "agent memory"

python -m paperpilot.cli.main review qc \
  --slug agent-memory \
  --topic "agent memory"

python -m paperpilot.cli.main review verify \
  --slug agent-memory \
  --topic "agent memory"

python -m paperpilot.cli.main review fetch-pdfs \
  --slug agent-memory \
  --topic "agent memory" \
  --unpaywall-email "you@example.com"

python -m paperpilot.cli.main review read \
  --slug agent-memory \
  --topic "agent memory" \
  --paper-id P001 \
  --force

python -m paperpilot.cli.main review matrix \
  --slug agent-memory \
  --topic "agent memory"
```

AI 精读编码后，可以先用 `curate` 自动筛掉明显偏题论文。默认是预览模式，只生成 curated CSV 和报告；确认后再加 `--apply` 覆盖 `paper_pool_coded.csv`，后续草稿会使用更新后的分层。

```bash
python -m paperpilot.cli.main review curate \
  --slug agent-memory \
  --topic "agent memory"

python -m paperpilot.cli.main review curate \
  --slug agent-memory \
  --topic "agent memory" \
  --exclude-keyword "clinical,epidemic,model cards" \
  --apply
```

也可以一条命令串起检索、Zotero 去重/新增、论文池构建、AI 精读编码和综述草稿：

```bash
python -m paperpilot.cli.main review run \
  --topic "agent memory" \
  --slug agent-memory \
  --collection-name "Review - Agent Memory" \
  --expand-queries \
  --prompt "long-term autonomous agent memory benchmark dataset survey" \
  --journals \
  --limit 30 \
  --use-deepxiv
```

如果希望运行更完整的综述自动化链路，可以加 `--full`。它会在 `read` 前尝试获取开放获取 PDF 并生成全文复核队列，在 `read` 后执行 curate、matrix、draft 和 qc。默认 curation 只生成预览；确认要覆盖编码表时再加 `--apply-curation`。

```bash
python -m paperpilot.cli.main review run \
  --topic "agent memory" \
  --slug agent-memory \
  --collection-name "Review - Agent Memory" \
  --expand-queries \
  --limit 30 \
  --full \
  --unpaywall-email "you@example.com"
```

默认产物在 `.review_projects/{slug}/`：

```text
research_plan.md
data/raw/paper_pool_raw.csv
data/processed/paper_pool_verified.csv
data/processed/paper_pool_coded.csv
data/processed/paper_pool_curated.csv
notes/core/*.md
bib/citation_keys.csv
bib/references.bib
reports/paper_pool_verification_report.md
reports/curation_report.md
reports/deep_reading_status.md
reports/review_draft.md
reports/qc_report.md
reports/fulltext_verification_status.md
reports/fulltext_fetch_status.md
reports/comparison_matrix.md
data/processed/fulltext_verification_queue.csv
data/processed/fulltext_fetch_report.csv
figs/taxonomy_overview.mmd
review_v1.md
```

`paper_pool_verified.csv` 会保留初筛元数据，包括 `source`、`dedupe_key`、`relevance_score`、`screening_decision`、`screening_reason` 和 `fulltext_status`，对应报告见 `reports/paper_pool_verification_report.md`。

## 当前状态

当前版本已经完成第一轮系统化建设：

- 业务主链路已存在
- orchestrator 已接入
- SQLite 状态层已接入
- summary / notion 支持基础增量跳过成功项
- 全量测试覆盖关键路径

## 后续增强方向

- watch 的 taxonomy / scoring / dedupe 增强
- item 级状态机与失败重试策略增强
- 更完整的顶级包入口与发布配置
- 更细的报表、日志、artifact 管理
