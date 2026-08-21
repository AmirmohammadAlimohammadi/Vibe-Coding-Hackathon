# Latest evaluation results

Evaluation date: 2026-08-21

## Retrieval baseline

Fourteen answerable bilingual cases were run against the live hybrid Qdrant collection.

| Metric | Result |
| --- | ---: |
| Hit@8 | 100% |
| Mean reciprocal rank | 0.7524 |
| Theme coverage | 100% across 6 tested themes |
| Latency p50 | 540 ms |
| Latency p95 | 939 ms |

## Full-agent comparison

Ten representative cases covered answers, clarification, refusal, memory, citations, and
personalization.

| Metric | Before | After |
| --- | ---: | ---: |
| Behavior accuracy | 100% | 100% |
| Citation validity | 100% | 100% |
| Retrieval hit rate | 100% | 100% |
| Average searches per turn | 1.4 | 1.2 |
| Estimated LLM calls | 25 | 21 |
| Latency p50 | 13.935 s | 11.535 s |
| Latency p95 | 16.933 s | 22.945 s |

The refinement reduced estimated LLM calls by 16%, average searches by 14%, and median
latency by 17%. The post-change p95 is not treated as a regression conclusion because ten
cases are too few for a stable tail-latency estimate and one answer had a slow refinement.

The optional LLM-judge run did not complete because the Avalai account returned
`insufficient_quota`. Correctness, completeness, groundedness, relevance, and personalization
scores therefore remain unreported rather than estimated.

## Cost-optimized retrieval

Nine technical golden queries were evaluated after enabling conservative sparse-first search.

| Metric | Cold sparse run | Warm Redis run |
| --- | ---: | ---: |
| Hit@8 | 100% | 100% |
| Paid embedding requests | 0 | 0 |
| Retrieval cache hit rate | 0% | 100% |
| Latency p50 | 5.22 ms | 0.63 ms |
| Latency p95 | 19.49 ms | 2.53 ms |

The combined decision-and-answer graph, Nano/Mini/Terra routing, answer cache, and actual token
telemetry are covered by deterministic tests. A new full semantic benchmark still requires
Avalai credit; the current account remains below the provider's minimum request cost.
