# Cost & Latency: Routing

All figures are rough estimates based on a frontier-tier model at approximately
$3/1M input tokens and $15/1M output tokens. Routing is the cheapest agent pattern
for classification + dispatch because it uses only 2 LLM calls with short outputs.

---

## At a Glance

|                          | Typical (P50 estimate) | High end (P95 estimate)                    |
|--------------------------|------------------------|--------------------------------------------|
| LLM calls per request    | 2 (classify + handle)  | 3 (fallback retry or handler escalation)   |
| Total input tokens       | ~600 - 2,000           | ~3,000+                                    |
| Total output tokens      | ~80 - 500              | ~1,000+                                    |
| Latency                  | ~0.6 - 2s              | ~2 - 4s                                    |
| Cost per 1,000 requests  | ~$0.30 - $1.50         | ~$3 - $8                                   |

Relative cost tier: Low. The classifier call is short and cheap. The handler call
varies based on what the handler does. If the handler itself is a complex pattern
(ReAct, RAG), the total cost is dominated by that handler, not the routing overhead.

---

## Call Breakdown

| Call         | Purpose                          | Est. input tokens | Est. output tokens |
|--------------|----------------------------------|-------------------|--------------------|
| Classifier   | Identify intent and select route | 200 - 600         | 30 - 80            |
| Handler      | Specialized response             | 300 - 1,500       | 100 - 500          |

The classifier call is intentionally short. It receives the user message and route
descriptions, and returns a route name and confidence score. This is one of the few
LLM calls where a smaller, cheaper model is often just as effective as a frontier model.

The handler call cost depends entirely on what the handler does. A simple FAQ handler
might add only 200 tokens. A handler that invokes a RAG pipeline adds a full RAG call.

---

## Latency Profile

Classifier call estimate: ~200 - 500ms
Handler call estimate: ~300 - 1,500ms (depends on handler complexity)

P50 estimate: ~0.6 - 2s
P95 estimate: ~2 - 4s (slow handler, complex response)

Routing adds approximately ~200 - 500ms of overhead (the classification call) on top
of the handler latency. For most use cases this is negligible. If the classification
overhead is unacceptable, consider using a smaller model or fine-tuned classifier.

---

## What Drives Cost Up

- Handler complexity. Routing itself is cheap, but the handler it selects can be
  expensive. A route that delegates to a Multi-Agent system has Multi-Agent costs.
  The routing overhead is typically under 5% of the total request cost.
- Number of routes described in the classifier prompt. If each route has a long
  description, the classifier prompt grows proportionally. With 10 verbose route
  descriptions, the classifier input can reach 800-1,200 tokens.
- Fallback handler usage. Routing to the fallback route means the classification
  was uncertain. If fallback usage is high, most requests are paying for classification
  without benefiting from specialized handling.
- Retries on low confidence. If you retry classification on low-confidence results
  with a stronger model, that retry can cost 2-5x the original classification call.

---

## What Drives Latency Up

- Handler latency (classifier latency is small by comparison)
- Classification retry on low confidence (doubles the classification time)
- Network latency on the classifier API call

---

## Cost Control Knobs

Use a smaller or cheaper model for classification. The classifier task is intent
matching, not complex reasoning. Models that are 5-10x cheaper than frontier models
typically perform comparably on well-defined route sets with clear descriptions.

Cache classification results for identical or near-identical inputs. If the same
question appears frequently ("What are your hours?"), the route is always the same.
An exact-match cache on the question string can skip the classifier call entirely.

Keep route descriptions concise and mutually exclusive. Long, overlapping descriptions
make classification harder (lower confidence, more retries) and more expensive (more
input tokens). Aim for 10-20 words per route description.

Build confidence-based routing without retries. Instead of retrying on low confidence,
route directly to the fallback handler. A fast, cheap fallback is better than a slow,
expensive retry in most production scenarios.

---

## Comparison to Related Patterns

| Pattern         | Est. LLM calls | Est. cost tier | Est. latency | Best when                                        |
|-----------------|----------------|----------------|--------------|--------------------------------------------------|
| Routing         | 2 (fixed)      | Low            | Low          | Classifiable intents, specialized handlers needed|
| Tool Use        | 2+ per round   | Low to Medium  | Low          | Structured function dispatch, no classification  |
| Orchestrator    | 2+N (dynamic)  | Medium to High | Medium       | Dynamic task decomposition, not classification   |
