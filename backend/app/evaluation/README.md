# Chatbot evaluation

This suite measures the parts of chatbot quality that can be tested before production:

- hybrid retrieval hit rate, reciprocal rank, theme coverage, and latency;
- answer, clarification, and refusal routing accuracy;
- citation presence and validity;
- conversation-memory and expertise-personalization behavior;
- optional 1–5 LLM-judge scores for correctness, relevance, completeness,
  groundedness, and personalization;
- actual provider tokens, LLM/embedding calls, cache hits, retrieval strategy, and latency.

Run the cheap retrieval baseline first:

```bash
docker compose exec backend python -m app.evaluation.run --mode retrieval
```

Run the complete agent on a representative subset:

```bash
docker compose exec backend python -m app.evaluation.run --mode full --limit 8
```

Add `--judge` for rubric-based answer scoring, or select cases with `--case CASE_ID`
and `--tag TAG`. Save machine-readable results with `--output /tmp/report.json`.

Run `python -m unittest app.evaluation.test_optimizations` inside the backend container to
verify combined-call routing, contextualization gating, usage extraction, and sparse gating.
Run retrieval twice to measure cold behavior and Redis cache hits separately.

Suggested release gates:

| Metric | Initial gate |
| --- | ---: |
| Retrieval hit@8 | >= 95% |
| Mean reciprocal rank | >= 0.75 |
| Behavior accuracy | >= 90% |
| Citation validity | 100% |
| Correctness and groundedness judge scores | >= 4.2/5 |
| Retrieval p95 latency | <= 3 seconds |

Production-only metrics such as goal completion, self-service rate, CSAT, bounce rate,
adoption, and cost per resolved conversation require telemetry and user feedback; they
cannot be estimated reliably from this offline suite.
