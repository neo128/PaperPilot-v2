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
