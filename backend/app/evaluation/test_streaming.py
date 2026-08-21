from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from app.chat.router import server_sent_event
from app.retrieval.agentic_rag import AgenticRagService, ExpertiseLevel, stream_chunk_text


class FakeStreamingModel:
    def stream(self, _messages):
        yield SimpleNamespace(content="Hello")
        yield SimpleNamespace(content=" world")
        yield SimpleNamespace(content=[{"type": "text", "text": "!"}])


class StreamingTests(unittest.TestCase):
    def test_stream_chunk_text_preserves_token_whitespace(self):
        self.assertEqual(stream_chunk_text(SimpleNamespace(content=" next")), " next")
        self.assertEqual(
            stream_chunk_text(
                SimpleNamespace(content=[{"type": "text", "text": " part"}])
            ),
            " part",
        )

    def test_stream_query_emits_tokens_and_completed_state(self):
        service = AgenticRagService.__new__(AgenticRagService)
        service.llm = FakeStreamingModel()
        service._prepare_state = lambda state: state
        service._answer_messages = lambda state: []

        events = list(
            service.stream_query(
                "question",
                0,
                expertise_level=ExpertiseLevel.INTERMEDIATE,
            )
        )

        self.assertEqual(
            [event["content"] for event in events[:-1]],
            ["Hello", " world", "!"],
        )
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(events[-1]["state"]["answer"], "Hello world!")

    def test_server_sent_event_is_valid_utf8_json_frame(self):
        frame = server_sent_event("token", {"content": " سلام"})
        event_line, data_line, _ = frame.split("\n", 2)

        self.assertEqual(event_line, "event: token")
        self.assertEqual(json.loads(data_line.removeprefix("data: ")), {"content": " سلام"})
        self.assertTrue(frame.endswith("\n\n"))


if __name__ == "__main__":
    unittest.main()
