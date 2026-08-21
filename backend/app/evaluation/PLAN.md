# Liara assistant evaluation plan

## Purpose

The scorecard separates search quality, agent decisions, answer quality, user outcomes,
reliability, and cost. A single metric such as containment can look good while users still
receive incomplete answers, so release decisions must use the combined scorecard.

## Test layers

### 1. Retrieval tests on every relevant change

- Run every answerable golden query against hybrid search.
- Measure hit rate at 5 and 8, mean reciprocal rank, per-theme coverage, and p50/p95 latency.
- Fail the release when a previously passing case loses its expected source.
- Add every confirmed production retrieval miss to `cases.json`.

### 2. Agent-policy tests before release

- **Answer:** sufficient context produces a direct, cited Markdown answer.
- **Clarify:** ambiguous relevant questions request only decisive missing details.
- **Refuse:** unrelated questions produce a concise localized admission of not knowing.
- **Memory:** follow-up questions resolve references from earlier turns.
- **Personalization:** beginner and advanced profiles receive materially different depth.
- **No repetition:** the agent does not ask for information already present in history.

### 3. Answer-quality tests nightly

Use an LLM judge and manually audit a stratified sample. Score correctness, relevance,
completeness, groundedness, and expertise fit from 1–5. The judge sees the expected facts
and retrieved sources, but its score is advisory: people review all failures, a random 10%
of passes, and disagreements between deterministic checks and the judge.

### 4. Safety and failure tests

- Prompt injection embedded in a retrieved chunk must not change system behavior.
- Unsupported, unrelated, and adversarial questions must not trigger general-knowledge answers.
- Invalid citations, leaked secrets, credentials, and personal data are automatic failures.
- Simulate Qdrant, embedding, LLM, Redis, and PostgreSQL timeouts and verify safe errors.
- Verify authentication, ownership isolation, request limits, and maximum input/context sizes.

## Golden-set design

The current seed has 18 Persian and English cases across PaaS, DBaaS, IaaS, object storage,
one-click apps, and CLI references. Grow it to at least 100 reviewed cases:

| Segment | Target share |
| --- | ---: |
| Simple factual and procedural | 30% |
| Complex multi-step and troubleshooting | 25% |
| Ambiguous questions requiring clarification | 15% |
| Conversation-memory follow-ups | 10% |
| Personalization pairs | 10% |
| Out-of-scope and adversarial | 10% |

Weight themes using real traffic once telemetry exists, while retaining minimum coverage for
low-volume products. Every case should contain expected behavior, accepted source paths,
critical facts, language, expertise level, and tags.

## Production telemetry

Emit one event per turn with a generated event ID and no raw secrets:

```json
{
  "event": "chat_turn_completed",
  "chat_id": "hashed-or-internal-id",
  "theme": "dbaas",
  "response_action": "answer",
  "search_count": 1,
  "source_count": 5,
  "latency_ms": 8200,
  "input_tokens": 0,
  "output_tokens": 0,
  "estimated_cost": 0,
  "user_feedback": null,
  "goal_completed": null,
  "escalated": false,
  "error_type": null
}
```

Add explicit helpful/not-helpful feedback and a resolved/not-resolved follow-up. Aggregate:

- self-service and escalation rates;
- goal completion and chatbot CSAT;
- fallback/refusal and repeated-question rates;
- median interaction depth, completion time, and session abandonment;
- adoption, monthly volume, and frequent-theme coverage;
- cost and token usage per completed conversation;
- error rate and p50/p95/p99 latency by dependency.

## Release gates

Initial gates should become stricter after collecting production data:

| Metric | Gate |
| --- | ---: |
| Retrieval hit@8 | >= 95% |
| Mean reciprocal rank | >= 0.75 |
| Agent behavior accuracy | >= 90% |
| Citation validity | 100% |
| Correctness and groundedness | >= 4.2/5 |
| Full-agent error rate | < 1% |
| Retrieval p95 latency | <= 3 seconds |

Do not set targets for containment, CSAT, completion, or cost until at least 200 real
conversations have been measured. Report confidence intervals and compare releases on the
same frozen golden set.
