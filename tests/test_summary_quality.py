from __future__ import annotations

from paperpilot.services.summary_quality import assess_summary_quality


GOOD_SUMMARY = """# 1. 论文基本信息
- 标题：3D-Mem: 3D Scene Memory for Embodied Exploration and Reasoning [原文]
- 年份：2024 [原文]
- 任务类型：具身探索、场景记忆、问答与目标导航 [原文]

# 2. 一句话总结
该论文提出 3D-Mem，用 Memory Snapshots 和 Frontier Snapshots 构建紧凑三维场景记忆，并在 A-EQA、EM-EQA 和 GOAT-Bench 上改进具身探索与推理表现。[原文]

# 3. 研究问题
具身智能体需要在部分可观测环境中长期保留空间、语义和探索边界信息；传统密集地图成本高，纯语言记忆又缺乏可操作空间结构。[原文]

# 4. 方法概述
系统输入 RGB-D 观测、位姿和探索轨迹，输出可检索的三维场景记忆与前沿节点。[原文]

# 5. 技术流程拆解（Step-by-step）
Step 1：从观测帧生成局部点云并融合语义标签。[原文]
Step 2：用 Memory Snapshots 保存代表性场景状态。[原文]
Step 3：用 Frontier Snapshots 表示待探索边界并服务于下一步规划。[原文]

# 6. 创新点评估（必须分级）
- Memory Snapshots：【创新类型】方法；【创新强度】中；【是否已有类似工作】有语义地图和场景图类似方向；【是否容易被替代】中。[推断]

# 7. 技术坐标系定位
方法位于表征学习与规划接口处，偏行为优化，同时保留可检索的机制化场景状态。[推断]

# 8. 实验与结果
论文在 A-EQA、EM-EQA 与 GOAT-Bench 上评估；A-EQA 相对改善约 29.8%，EM-EQA 改善约 28.1%，GOAT-Bench 上也有 8.2% 和 5.1% 的指标提升。[原文]

# 9. 局限性
作者实验集中在既定模拟基准，真实机器人部署仍需进一步验证。[推断]

# 10. 失败模式（关键）
若语义分割错误或探索前沿估计漂移，记忆检索会把错误空间状态注入规划。[推断]

# 11. 通用复用价值
适合用于具身记忆、主动探索、场景图、长程任务规划综述。[启发]

# 12. 分类标签（结构化）
任务类型：具身探索；方法类型：三维场景记忆；是否使用视觉：是；是否涉及记忆/语义表示：是。[原文]

# 15. 高质量证据片段（强约束）
- 中文证据转述：论文明确提出紧凑且信息丰富的三维场景记忆结构；定位短语：compact and informative 3D scene memory；支撑结论：3D-Mem 的核心贡献是可检索场景记忆；为什么能支撑：该短语直接描述方法目标。[原文]
- 中文证据转述：实验覆盖 A-EQA、EM-EQA 和 GOAT-Bench；定位短语：A-EQA, EM-EQA, GOAT-Bench；支撑结论：评估跨问答与导航任务；为什么能支撑：这些基准对应不同具身推理场景。[原文]
"""


def test_good_summary_scores_as_reusable():
    report = assess_summary_quality(GOOD_SUMMARY, source="pdf", locale="zh")

    assert report.score >= 70
    assert report.label in {"usable", "good"}
    assert report.source_coverage == "pdf_text"


def test_metadata_card_is_flagged_even_when_long_enough():
    markdown = (
        "# 1. 论文基本信息\n"
        "当前批量总结：题名和元数据表明，这篇论文可能与智能体记忆有关。\n"
        "中文题名辅助理解：人工智能智能体时代的记忆。\n"
        "需要进一步阅读全文确认具体方法、实验、baseline 和指标。\n"
    ) * 20

    report = assess_summary_quality(markdown, source="pdf", locale="zh")

    assert report.label == "metadata_card"
    assert report.score < 50
    assert any("模板化" in finding for finding in report.findings)


def test_english_heavy_summary_is_flagged_for_chinese_locale():
    markdown = """# 1. 论文基本信息
Title: Test Paper [原文]

# 2. 一句话总结
This paper proposes a memory architecture for embodied agents with modules, policies, experiments, and evaluations.
It includes long English prose that should have been translated into Chinese for the canonical summary.

# 15. 高质量证据片段
Evidence: memory architecture.
"""

    report = assess_summary_quality(markdown, source="abstract", locale="zh")

    assert report.score < 70
    assert any("中文占比" in finding for finding in report.findings)


def test_abstract_only_is_never_canonical_quality():
    markdown = """# 摘要卡

来源覆盖：abstract_only。来源限制：当前仅获得摘要，未获得开放全文。

这篇论文提出一个机器人系统，但缺少完整实验细节。[原文]
"""

    report = assess_summary_quality(markdown, source="abstract", locale="zh")

    assert report.label == "abstract_card"
    assert report.source_coverage == "abstract_only"
    assert report.score <= 55


def test_truncated_pdf_excerpt_is_flagged():
    markdown = GOOD_SUMMARY + "\n\n…（片段已截断，仅基于此生成）"

    report = assess_summary_quality(markdown, source="pdf_excerpt", locale="zh")

    assert report.label == "excerpt_card"
    assert report.source_coverage == "pdf_excerpt"
    assert report.score <= 60
