import unittest

from paperpilot.clients.ai import AIClient


class CapturingAIClient(AIClient):
    def __init__(self):
        self.last_messages = None
        self.last_kwargs = None

    def chat(self, messages, model=None, **kwargs):
        self.last_messages = messages
        self.last_kwargs = {"model": model, **kwargs}
        return " generated summary "


class AIClientPromptTest(unittest.TestCase):
    def test_chinese_summary_prompt_uses_review_oriented_template(self):
        ai = CapturingAIClient()

        result = ai.summarize_paper_excerpt(
            title="Robot Paper",
            text="This paper proposes a VLA method for long-horizon robot tasks.",
            locale="zh",
            max_chars=12000,
            model="test-model",
        )

        self.assertEqual(result, "generated summary")
        self.assertIsNotNone(ai.last_messages)
        system_msg = ai.last_messages[0]["content"]
        prompt = ai.last_messages[1]["content"]

        self.assertIn("科研论文分析助手", system_msg)
        self.assertIn("所有内容必须标注来源类型：[原文] / [推断] / [启发]", prompt)
        self.assertIn("禁止编造论文中未出现的信息", prompt)
        self.assertIn("原文片段未提供", prompt)
        self.assertIn("## 1. 论文基本信息", prompt)
        self.assertIn("## 6. 创新点评估", prompt)
        self.assertIn("## 11. 综述价值", prompt)
        self.assertIn("## 13. 具身智能专用分析", prompt)
        self.assertIn("## 15. 高质量证据片段", prompt)
        self.assertIn("论文标题：Robot Paper", prompt)
        self.assertIn("用户提供的论文内容", prompt)
        self.assertEqual(ai.last_kwargs["model"], "test-model")
        self.assertEqual(ai.last_kwargs["temperature"], 0.15)

    def test_structured_reading_prompt_requires_grounded_topic_fit(self):
        ai = CapturingAIClient()

        result = ai.read_paper_structured(
            topic="active exploration with world models in embodied AI",
            title="Static Analysis Paper",
            metadata={"year": "2026"},
            context="This paper studies static analysis for Rust programs.",
            locale="zh",
            max_chars=12000,
            model="test-model",
        )

        self.assertEqual(result, "generated summary")
        self.assertIsNotNone(ai.last_messages)
        prompt = ai.last_messages[1]["content"]

        self.assertIn("有边界的证据包", prompt)
        self.assertIn("间接相关/弱相关", prompt)
        self.assertIn("不要强行称其为主动探索或世界模型论文", prompt)
        self.assertIn("不要泛泛写“PDF截断”", prompt)
        self.assertIn("needs_verification 必须绑定到具体缺失项", prompt)
        self.assertIn("不得把跨域启发写成作者贡献", prompt)

    def test_review_coding_prompt_constrains_scores_and_tiers(self):
        ai = CapturingAIClient()

        result = ai.code_paper_for_review(
            topic="active exploration with world models in embodied AI",
            title="Indirect Benchmark Paper",
            metadata={"venue": "arXiv"},
            context="The paper proposes a benchmark.",
            reading_note="Indirectly related.",
            locale="zh",
            max_chars=12000,
            model="test-model",
        )

        self.assertEqual(result, {})
        self.assertIsNotNone(ai.last_messages)
        prompt = ai.last_messages[1]["content"]

        self.assertIn("priority_score must be an integer from 0 to 100", prompt)
        self.assertIn("coding_confidence must be one of high, medium, low, needs_verification", prompt)
        self.assertIn("A paper should be A only if it directly studies active exploration with world models in embodied AI", prompt)
        self.assertIn("C for indirect baselines/surveys", prompt)
        self.assertIn("Do not upgrade an indirect paper by speculative relation", prompt)


if __name__ == "__main__":
    unittest.main()
