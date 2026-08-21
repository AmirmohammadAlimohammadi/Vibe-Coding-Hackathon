from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from app.retrieval.agentic_rag import AgenticRagService, message_text
from app.retrieval.hybrid import HybridRetriever, RetrievedChunk


CASES_PATH = Path(__file__).with_name("cases.json")
VALID_BEHAVIORS = {"answer", "clarify", "refuse"}
CITATION_PATTERN = re.compile(r"\[Source\s+(\d+)\]", re.IGNORECASE)

JUDGE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are evaluating a documentation-grounded hosting assistant. Score only
the assistant response against the supplied reference facts and sources. Do not reward
unsupported general knowledge. Each score is an integer from 1 to 5.

Return JSON only with this exact shape:
{{"correctness": 1, "relevance": 1, "completeness": 1, "groundedness": 1,
 "personalization": 1, "reason": "one short explanation"}}

Scoring criteria:
- correctness: factual claims agree with the references
- relevance: directly addresses the user's request without unnecessary material
- completeness: includes the expected facts needed to complete the task
- groundedness: factual claims are supported by the supplied sources
- personalization: explanation matches the requested expertise level

For expected clarification, reward a focused question for decisive missing details. For
expected refusal, reward a concise admission of not knowing and penalize answering anyway.""",
        ),
        (
            "human",
            "Question:\n{question}\n\nExpected behavior: {expected_behavior}"
            "\nExpertise: {expertise_level}\nExpected facts:\n{expected_facts}"
            "\n\nSources:\n{sources}\n\nAssistant response:\n{answer}",
        ),
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Liara chatbot retrieval and agent behavior."
    )
    parser.add_argument("--mode", choices=("retrieval", "full"), default="retrieval")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--tag", action="append", dest="tags")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--max-refinements", type=int, default=2)
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("Evaluation cases must be a JSON list")
    seen_ids: set[str] = set()
    for case in cases:
        case_id = case.get("id")
        behavior = case.get("expected_behavior")
        if not case_id or case_id in seen_ids:
            raise ValueError(f"Missing or duplicate case id: {case_id!r}")
        if behavior not in VALID_BEHAVIORS:
            raise ValueError(f"Invalid expected behavior in {case_id}: {behavior!r}")
        seen_ids.add(case_id)
    return cases


def select_cases(cases: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    selected = cases
    if args.case_ids:
        wanted = set(args.case_ids)
        selected = [case for case in selected if case["id"] in wanted]
        missing = wanted - {case["id"] for case in selected}
        if missing:
            raise ValueError(f"Unknown case ids: {', '.join(sorted(missing))}")
    if args.tags:
        wanted_tags = set(args.tags)
        selected = [case for case in selected if wanted_tags.intersection(case.get("tags", []))]
    if args.mode == "retrieval":
        selected = [case for case in selected if case.get("expected_source_paths")]
    if args.limit > 0:
        selected = selected[: args.limit]
    if not selected:
        raise ValueError("No evaluation cases matched the requested filters")
    return selected


def normalized_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("/").casefold()


def expected_rank(documents: list[RetrievedChunk], expected_paths: list[str]) -> int | None:
    expected = [normalized_path(path) for path in expected_paths]
    for rank, document in enumerate(documents, start=1):
        actual = normalized_path(document.source_path)
        if any(actual == path or actual.endswith(path) for path in expected):
            return rank
    return None


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_value
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def rate(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / denominator, 4) if denominator else 0.0


def behavior_from_state(state: dict[str, Any]) -> str:
    if not state["relevant"]:
        return "refuse"
    return "answer" if state["sufficient"] else "clarify"


def citation_metrics(answer: str, source_count: int, expected_behavior: str) -> dict[str, Any]:
    citation_numbers = [int(value) for value in CITATION_PATTERN.findall(answer)]
    invalid = [value for value in citation_numbers if value < 1 or value > source_count]
    citation_required = expected_behavior == "answer"
    valid = not invalid and (not citation_required or bool(citation_numbers))
    return {
        "citation_count": len(citation_numbers),
        "citation_valid": valid,
        "invalid_citations": invalid,
    }


def source_snapshot(documents: list[RetrievedChunk]) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "path": document.source_path,
            "title": document.document_title,
            "score": round(document.score, 6),
        }
        for rank, document in enumerate(documents, start=1)
    ]


def judge_response(
    service: AgenticRagService,
    case: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    source_text = service._context(state["documents"])
    response = service.llm.invoke(
        JUDGE_PROMPT.format_messages(
            question=case["question"],
            expected_behavior=case["expected_behavior"],
            expertise_level=case.get("expertise_level", "intermediate"),
            expected_facts="\n".join(f"- {fact}" for fact in case.get("expected_facts", [])),
            sources=source_text,
            answer=state["answer"],
        )
    )
    output = message_text(response)
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", output, re.DOTALL)
    payload = fenced.group(1) if fenced else output
    parsed = json.loads(payload)
    scores = {}
    for name in ("correctness", "relevance", "completeness", "groundedness", "personalization"):
        scores[name] = max(1, min(5, int(parsed[name])))
    scores["reason"] = str(parsed.get("reason", ""))[:500]
    return scores


def run_retrieval(cases: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    retriever = HybridRetriever()
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        query = case.get("retrieval_query", case["question"])
        started = time.perf_counter()
        try:
            documents = retriever.search(query, limit=top_k)
        except Exception as error:
            latency_ms = (time.perf_counter() - started) * 1000
            results.append(
                {
                    "id": case["id"],
                    "theme": case["theme"],
                    "query": query,
                    "hit": False,
                    "first_relevant_rank": None,
                    "reciprocal_rank": 0.0,
                    "latency_ms": round(latency_ms, 2),
                    "sources": [],
                    "error_type": type(error).__name__,
                    "error": str(error)[:1000],
                }
            )
            print(
                f"[{index}/{len(cases)}] {case['id']}: ERROR {type(error).__name__}",
                flush=True,
            )
            continue
        latency_ms = (time.perf_counter() - started) * 1000
        rank = expected_rank(documents, case["expected_source_paths"])
        result = {
            "id": case["id"],
            "theme": case["theme"],
            "query": query,
            "hit": rank is not None,
            "first_relevant_rank": rank,
            "reciprocal_rank": round(1 / rank, 4) if rank else 0.0,
            "latency_ms": round(latency_ms, 2),
            "sources": source_snapshot(documents),
        }
        results.append(result)
        print(
            f"[{index}/{len(cases)}] {case['id']}: "
            f"{'hit@' + str(rank) if rank else 'MISS'} ({latency_ms:.0f} ms)",
            flush=True,
        )

    latencies = [result["latency_ms"] for result in results]
    theme_results: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        theme_results[result["theme"]].append(result)
    return {
        "mode": "retrieval",
        "case_count": len(results),
        "metrics": {
            f"hit_rate_at_{top_k}": rate(sum(result["hit"] for result in results), len(results)),
            "mean_reciprocal_rank": round(
                sum(result["reciprocal_rank"] for result in results) / len(results), 4
            ),
            "latency_ms_p50": round(percentile(latencies, 0.5), 2),
            "latency_ms_p95": round(percentile(latencies, 0.95), 2),
            "theme_coverage": {
                theme: rate(sum(item["hit"] for item in items), len(items))
                for theme, items in sorted(theme_results.items())
            },
            "error_rate": rate(sum("error" in result for result in results), len(results)),
        },
        "results": results,
    }


def run_full(
    cases: list[dict[str, Any]],
    max_refinements: int,
    use_judge: bool,
) -> dict[str, Any]:
    service = AgenticRagService()
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        started = time.perf_counter()
        try:
            state = service.query(
                case["question"],
                max_refinements=max_refinements,
                history=case.get("history", []),
                expertise_level=case.get("expertise_level", "intermediate"),
            )
        except Exception as error:
            latency_ms = (time.perf_counter() - started) * 1000
            results.append(
                {
                    "id": case["id"],
                    "theme": case["theme"],
                    "expected_behavior": case["expected_behavior"],
                    "actual_behavior": "error",
                    "behavior_correct": False,
                    "retrieval_hit": None,
                    "citation_valid": False,
                    "latency_ms": round(latency_ms, 2),
                    "search_count": 0,
                    "estimated_llm_calls": 0,
                    "error_type": type(error).__name__,
                    "error": str(error)[:1000],
                }
            )
            print(
                f"[{index}/{len(cases)}] {case['id']}: ERROR {type(error).__name__}",
                flush=True,
            )
            continue
        latency_ms = (time.perf_counter() - started) * 1000
        actual_behavior = behavior_from_state(state)
        rank = expected_rank(state["documents"], case.get("expected_source_paths", []))
        citations = citation_metrics(
            state["answer"], len(state["documents"]), case["expected_behavior"]
        )
        result = {
            "id": case["id"],
            "theme": case["theme"],
            "expected_behavior": case["expected_behavior"],
            "actual_behavior": actual_behavior,
            "behavior_correct": actual_behavior == case["expected_behavior"],
            "retrieval_hit": rank is not None if case.get("expected_source_paths") else None,
            "first_relevant_rank": rank,
            "latency_ms": round(latency_ms, 2),
            "search_count": len(state["attempts"]),
            "estimated_llm_calls": (
                len(state["attempts"])
                + int(state["relevant"])
                + int(bool(case.get("history")))
            ),
            "answer_characters": len(state["answer"]),
            "final_search_query": state["search_query"],
            "attempts": state["attempts"],
            "answer": state["answer"],
            "sources": source_snapshot(state["documents"]),
            **citations,
        }
        if use_judge:
            try:
                result["judge"] = judge_response(service, case, state)
            except Exception as error:
                result["judge_error_type"] = type(error).__name__
                result["judge_error"] = str(error)[:1000]
        results.append(result)
        print(
            f"[{index}/{len(cases)}] {case['id']}: expected={case['expected_behavior']} "
            f"actual={actual_behavior} ({latency_ms:.0f} ms)",
            flush=True,
        )

    latencies = [result["latency_ms"] for result in results]
    expected_counts = Counter(result["expected_behavior"] for result in results)
    correct_counts = Counter(
        result["expected_behavior"] for result in results if result["behavior_correct"]
    )
    judged = [result["judge"] for result in results if "judge" in result]
    metrics: dict[str, Any] = {
        "behavior_accuracy": rate(sum(result["behavior_correct"] for result in results), len(results)),
        "behavior_accuracy_by_type": {
            behavior: rate(correct_counts[behavior], expected_counts[behavior])
            for behavior in sorted(expected_counts)
        },
        "fallback_rate": rate(sum(result["actual_behavior"] == "refuse" for result in results), len(results)),
        "clarification_rate": rate(sum(result["actual_behavior"] == "clarify" for result in results), len(results)),
        "citation_validity_rate": rate(sum(result["citation_valid"] for result in results), len(results)),
        "retrieval_hit_rate": rate(
            sum(result["retrieval_hit"] is True for result in results),
            sum(result["retrieval_hit"] is not None for result in results),
        ),
        "average_searches": round(
            sum(result["search_count"] for result in results) / len(results), 2
        ),
        "estimated_llm_calls": sum(result["estimated_llm_calls"] for result in results),
        "error_rate": rate(sum("error" in result for result in results), len(results)),
        "judge_error_rate": rate(
            sum("judge_error" in result for result in results), len(results)
        ) if use_judge else 0.0,
        "latency_ms_p50": round(percentile(latencies, 0.5), 2),
        "latency_ms_p95": round(percentile(latencies, 0.95), 2),
    }
    if judged:
        metrics["judge_scores"] = {
            name: round(sum(item[name] for item in judged) / len(judged), 2)
            for name in ("correctness", "relevance", "completeness", "groundedness", "personalization")
        }
        metrics["judge_case_count"] = len(judged)
    return {"mode": "full", "case_count": len(results), "metrics": metrics, "results": results}


def main() -> None:
    args = parse_args()
    cases = select_cases(load_cases(args.cases), args)
    report = (
        run_retrieval(cases, args.top_k)
        if args.mode == "retrieval"
        else run_full(cases, args.max_refinements, args.judge)
    )
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"Report written to {args.output}", flush=True)
    print(output)


if __name__ == "__main__":
    main()
