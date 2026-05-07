可以把原来的 `agent memory` 参数改成面向 **Embodied AI World Models / 具身智能世界模型** 的综述检索。当前比较好的检索主线应覆盖：世界模型统一定义、VLA/world model 结合、机器人操作/导航、数据集与 benchmark、物理一致性、长时序一致性、主动探索与闭环控制。近期综述也基本沿着这些方向组织，例如有综述将 embodied world model 按 **Functionality / Temporal Modeling / Spatial Representation** 三个轴分类，并系统整理数据资源与评测指标。([arXiv][1])

## 推荐主命令：综合综述版

```bash
python -m paperpilot.cli.main review run \
  --topic "embodied AI world models" \
  --slug embodied-world-models \
  --collection-name "Review - Embodied AI World Models" \
  --expand-queries \
  --prompt "embodied AI world models robotics vision-language-action VLA agents robot manipulation navigation model-based reinforcement learning latent dynamics RSSM Dreamer video prediction diffusion world model 3D spatial representation physical consistency long-horizon temporal consistency planning control active exploration datasets benchmarks evaluation metrics survey" \
  --journals \
  --limit 80 \
  --use-deepxiv
```

## 参数逐项修改建议

| 参数                  | 原参数                                                            | 建议参数                                  | 原因                                        |
| ------------------- | -------------------------------------------------------------- | ------------------------------------- | ----------------------------------------- |
| `--topic`           | `"agent memory"`                                               | `"embodied AI world models"`          | 主题需要从智能体记忆切换到具身智能世界模型                     |
| `--slug`            | `agent-memory`                                                 | `embodied-world-models`               | 便于生成独立 review 目录/任务 ID                    |
| `--collection-name` | `"Review - Agent Memory"`                                      | `"Review - Embodied AI World Models"` | Zotero/Notion/数据库中更容易归档                   |
| `--prompt`          | `"long-term autonomous agent memory benchmark dataset survey"` | 见上方长 prompt                           | prompt 应覆盖模型、任务、数据、评测和落地路线                |
| `--limit`           | `30`                                                           | `80` 或 `100`                          | 世界模型/VLA/机器人/benchmark 交叉文献多，30 篇容易漏掉关键论文 |
| `--expand-queries`  | 保留                                                             | 保留                                    | 该主题关键词分散，需要 query expansion               |
| `--journals`        | 保留或视情况去掉                                                       | 建议初次保留                                | 用于召回综述/期刊/正式论文；若想追最新 arXiv，可再跑一版不加该参数     |
| `--use-deepxiv`     | 保留                                                             | 保留                                    | 对 arXiv/DeepXiv 类论文发现有帮助                  |

---

## 更适合你研究目标的 4 个细分脚本

### 1. 总览与技术分类版

适合先建立综述框架、分类体系、代表路线。

```bash
python -m paperpilot.cli.main review run \
  --topic "taxonomy of world models for embodied AI" \
  --slug embodied-world-model-taxonomy \
  --collection-name "Review - Embodied World Model Taxonomy" \
  --expand-queries \
  --prompt "world models for embodied AI taxonomy survey robotics VLA agents decision-coupled world models general-purpose world models temporal modeling sequential simulation global difference prediction spatial representation latent vector token features spatial latent grid 3D world model decomposed rendering physical dynamics" \
  --journals \
  --limit 60 \
  --use-deepxiv
```

### 2. VLA + World Model 版

适合研究“世界模型如何增强 VLA 的规划、推演、纠错、泛化”。

```bash
python -m paperpilot.cli.main review run \
  --topic "world models for vision-language-action agents" \
  --slug world-models-for-vla-agents \
  --collection-name "Review - World Models for VLA Agents" \
  --expand-queries \
  --prompt "world models for vision-language-action agents VLA robotics embodied AI robot foundation models future prediction action-conditioned video prediction planning with world models robot manipulation long-horizon tasks closed-loop control policy learning physical reasoning generalization evaluation benchmark dataset survey" \
  --journals \
  --limit 80 \
  --use-deepxiv
```

### 3. 数据集与 Benchmark 版

适合你后续做 RoboXStudio / RoboDriver / 具身数据飞轮时使用，重点看评测指标、数据 schema、数据质量。

```bash
python -m paperpilot.cli.main review run \
  --topic "datasets and benchmarks for embodied world models" \
  --slug embodied-world-model-datasets-benchmarks \
  --collection-name "Review - Embodied World Model Datasets and Benchmarks" \
  --expand-queries \
  --prompt "embodied world model datasets benchmarks evaluation metrics robotics datasets VLA datasets robot manipulation benchmark simulation real robot data Open X-Embodiment DROID LIBERO RoboCasa ManiSkill RLDS LeRobot physical consistency temporal consistency spatial reasoning affordance prediction action-conditioned prediction task success data quality survey" \
  --journals \
  --limit 80 \
  --use-deepxiv
```

### 4. 主动探索 + 世界模型版

如果你的重点是“未知环境主动探索范式”，这一版最贴近你的研究方向。

```bash
python -m paperpilot.cli.main review run \
  --topic "active exploration with world models in embodied AI" \
  --slug active-exploration-world-models \
  --collection-name "Review - Active Exploration and World Models" \
  --expand-queries \
  --prompt "active exploration with world models embodied AI robotics curiosity intrinsic motivation model-based reinforcement learning uncertainty estimation information gain active perception exploration policy latent dynamics RSSM Dreamer world model planning robot navigation manipulation unknown environments self-improvement closed-loop learning benchmark survey" \
  --journals \
  --limit 80 \
  --use-deepxiv
```

---

## 我建议你第一轮这样跑

先跑 **总览版** 和 **数据集 Benchmark 版**，再跑 **VLA + World Model 版**：

```bash
# 1. 总览分类
python -m paperpilot.cli.main review run \
  --topic "taxonomy of world models for embodied AI" \
  --slug embodied-world-model-taxonomy \
  --collection-name "Review - Embodied World Model Taxonomy" \
  --expand-queries \
  --prompt "world models for embodied AI taxonomy survey robotics VLA agents decision-coupled world models general-purpose world models temporal modeling sequential simulation global difference prediction spatial representation latent vector token features spatial latent grid 3D world model decomposed rendering physical dynamics" \
  --journals \
  --limit 60 \
  --use-deepxiv

# 2. 数据集与评测
python -m paperpilot.cli.main review run \
  --topic "datasets and benchmarks for embodied world models" \
  --slug embodied-world-model-datasets-benchmarks \
  --collection-name "Review - Embodied World Model Datasets and Benchmarks" \
  --expand-queries \
  --prompt "embodied world model datasets benchmarks evaluation metrics robotics datasets VLA datasets robot manipulation benchmark simulation real robot data Open X-Embodiment DROID LIBERO RoboCasa ManiSkill RLDS LeRobot physical consistency temporal consistency spatial reasoning affordance prediction action-conditioned prediction task success data quality survey" \
  --journals \
  --limit 80 \
  --use-deepxiv

# 3. VLA + 世界模型
python -m paperpilot.cli.main review run \
  --topic "world models for vision-language-action agents" \
  --slug world-models-for-vla-agents \
  --collection-name "Review - World Models for VLA Agents" \
  --expand-queries \
  --prompt "world models for vision-language-action agents VLA robotics embodied AI robot foundation models future prediction action-conditioned video prediction planning with world models robot manipulation long-horizon tasks closed-loop control policy learning physical reasoning generalization evaluation benchmark dataset survey" \
  --journals \
  --limit 80 \
  --use-deepxiv
```

这里的设计逻辑是：第一轮先拿到综述框架；第二轮补数据、benchmark、指标；第三轮聚焦 VLA/机器人落地。这样后续更容易整理成“问题定义—技术路线—数据资源—评测体系—工程落地—开放问题”的综述结构。

[1]: https://arxiv.org/abs/2510.16732?utm_source=chatgpt.com "A Comprehensive Survey on World Models for Embodied AI"
