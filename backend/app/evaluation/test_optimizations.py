from __future__ import annotations

import unittest

from app.retrieval.agentic_rag import (
    AgenticRagService,
    ExpertiseLevel,
    empty_usage,
    localized_unknown,
    message_usage,
    tagged_value,
)
from app.retrieval.cache import normalize_cache_text
from app.retrieval.hybrid import HybridRetriever


class FakeMessage:
    usage_metadata = {
        "input_tokens": 120,
        "output_tokens": 30,
        "total_tokens": 150,
    }

    def __init__(self, content: str = "") -> None:
        self.content = content


class FakeLlm:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    def invoke(self, _) -> FakeMessage:
        self.calls += 1
        return FakeMessage(self.content)


class CostOptimizationTests(unittest.TestCase):
    def test_cache_normalization_handles_persian_and_whitespace(self) -> None:
        self.assertEqual(normalize_cache_text("  كد\n  يک  "), "کد یک")

    def test_usage_metadata_is_recorded(self) -> None:
        usage = message_usage(FakeMessage())
        self.assertEqual(usage["input_tokens"], 120)
        self.assertEqual(usage["output_tokens"], 30)
        self.assertEqual(usage["total_tokens"], 150)
        self.assertEqual(usage["llm_calls"], 1)

    def test_tagged_response_parsing_preserves_markdown(self) -> None:
        output = "<ACTION>answer</ACTION><ANSWER>## Test\n`code`</ANSWER>"
        self.assertEqual(tagged_value(output, "ACTION"), "answer")
        self.assertEqual(tagged_value(output, "ANSWER"), "## Test\n`code`")

    def test_only_context_dependent_followups_are_rewritten(self) -> None:
        history = [{"role": "user", "content": "Redis"}]
        self.assertTrue(
            AgenticRagService._needs_contextualization("حالا چطور به آن وصل شوم؟", history)
        )
        self.assertFalse(
            AgenticRagService._needs_contextualization(
                "چطور یک برنامه React را روی لیارا مستقر کنم؟",
                history,
            )
        )

    def test_refinement_route_stops_after_budget(self) -> None:
        base = {
            "action": "refine",
            "max_refinements": 1,
            "attempts": [{"query": "one"}],
        }
        self.assertEqual(AgenticRagService._route_after_response(base), "rewrite")
        self.assertEqual(
            AgenticRagService._route_after_response(
                {**base, "attempts": [{"query": "one"}, {"query": "two"}]}
            ),
            "done",
        )

    def test_sparse_bypass_requires_distinctive_term(self) -> None:
        self.assertIn("redis_uri", HybridRetriever._distinctive_terms("Use REDIS_URI"))
        self.assertFalse(HybridRetriever._distinctive_terms("How do I deploy an app?"))

    def test_sensitive_questions_are_not_answer_cached(self) -> None:
        self.assertFalse(AgenticRagService._cacheable_question("password is abc", []))
        self.assertTrue(
            AgenticRagService._cacheable_question("How do I deploy React?", [])
        )

    def test_localized_refusal_has_no_model_cost(self) -> None:
        self.assertEqual(localized_unknown("هوای فردا"), "نمی‌دانم.")
        self.assertEqual(localized_unknown("weather"), "I don't know.")
        self.assertEqual(empty_usage()["total_tokens"], 0)

    def test_combined_decision_and_answer_uses_one_llm_call(self) -> None:
        output = """<RELEVANCE>relevant</RELEVANCE>
<VERDICT>sufficient</VERDICT>
<ACTION>answer</ACTION>
<REFINED_QUERY>NONE</REFINED_QUERY>
<REASON>Enough context.</REASON>
<ANSWER>Use `liara deploy`. [Source 1]</ANSWER>"""
        fake_llm = FakeLlm(output)
        service = AgenticRagService.__new__(AgenticRagService)
        service.simple_model_name = "cheap-model"
        service.complex_model_name = "expensive-model"
        service.answer_llms = {
            "cheap-model": fake_llm,
            "expensive-model": fake_llm,
        }
        state = {
            "question": "How do I deploy?",
            "history": [],
            "search_query": "How do I deploy?",
            "max_refinements": 1,
            "documents": [],
            "attempts": [],
            "expertise_level": ExpertiseLevel.INTERMEDIATE,
            "retrieval_strategy": "sparse",
            "usage": empty_usage(),
            "models_used": [],
        }
        result = service._respond(state)
        self.assertEqual(result["action"], "answer")
        self.assertEqual(result["answer"], "Use `liara deploy`. [Source 1]")
        self.assertEqual(result["usage"]["llm_calls"], 1)
        self.assertEqual(fake_llm.calls, 1)


if __name__ == "__main__":
    unittest.main()
