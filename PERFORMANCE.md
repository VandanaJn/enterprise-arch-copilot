# Incident-path latency: what was measured, changed, and learned

A record of one optimization pass on the incident path. Decisions are in
[DECISIONS.md](DECISIONS.md); this document holds the numbers, the method, and the
things that turned out to be wrong.

**Result: `/chat` average 18.9s → 10.2s on live traffic, eval p95 19.3s → 10.5s (-45%).**
Answer quality mostly held, with one open regression on incident factuality that is
partly explained by pre-existing routing defects.

---

## 1. Starting point

`/metrics/summary` reported:

```json
"chat_latency":    {"count": 4, "avg_seconds": 18.87},
"overall_latency": {"count": 7, "p50_seconds": 1.25, "p95_seconds": 49.5, "p99_seconds": 57.9}
```

The p95 and p99 there were computed from **7 observations** and were noise, an artifact
of Prometheus bucket edges. The trustworthy figure was the 18.87s average, corroborated
by a 103-example eval run at p50 3.84s / p95 19.32s.

That spread is the important part: the workload is **bimodal**, not uniformly slow.
General questions and declines returned in ~4s. Incident questions cost ~19s.

## 2. Method

Optimize nothing until the total can be attributed to a step.

Two histograms were added, measured at the SSE stream boundary rather than inside the
graph (`eac_node_duration_seconds{node}`, `eac_time_to_first_token_seconds`). LangGraph
emits an `updates` payload as each node finishes, so the gap between updates is that
node's wall clock. `src/agent.py` needed no metrics import.

Everything below was then measured three ways, and the three had to agree before a
change was believed:

| method | what it gives | cost |
|---|---|---|
| local probe, 3 runs, one question | per-node wall clock, tool counts, TTFT | cents |
| A/B probe, feature forced off in-process | isolates one change | cents |
| full eval, 103 examples, LLM judges | quality + latency percentiles | ~5 min, a few dollars |

## 3. Where the 19s actually went

First probe, warm-adjusted (the 3.40s injection check was cold-start model loading, and
is 0.06s in a warmed server):

| step | seconds | LLM calls |
|---|---|---|
| `validate_input` | 0.11 | 0 |
| `prompt_injection_check` | ~0.2 | 0 |
| `triage` | 2.27 | 1 |
| `structured_agent` | 4.99 | 4 (2 SQL + 1 incidents + final) |
| `runbook_agent` | 6.19 | 2 (+0.5s search) |
| `synthesize` | 4.81 | 1 |
| **total** | **~18.4** | **~8 sequential** |

**Retrieval was never the bottleneck.** Supporting measurements:

- SQLite queries: `service_catalog` 0.31ms, `api_endpoints` 0.07ms, `incidents` 0.07ms.
- A full `search_engineering_docs` call: 0.44-0.86s, mostly the OpenAI embedding round trip.
- Three doc searches already ran **in parallel**: sum of durations 1.23s, wall clock 0.47s,
  a 2.6x speedup, on three distinct threads. The model batches them into one AI message
  and LangGraph's `ToolNode` fans them out via `executor.map`. Nothing to win there.

The cost was ~8 **sequential LLM round trips** at 1-5s each. That reframed the whole
problem: the fix is to remove round trips, not to speed up I/O.

## 4. Changes, and what each was worth

### 4a. Preload the service catalog (`structured_agent`)

The catalog is small: 10 services (~341 tokens), 24 endpoints (~491 tokens). The agent
was spending 4 LLM round trips *discovering* facts that fit in ~550 tokens.

A/B on the same question, 3 runs per arm, same process:

| arm | total | TTFT | `structured_agent` | tool calls/run |
|---|---|---|---|---|
| snapshot **on** | 12.82s | 8.95s | **1.90s** | 2.3 |
| snapshot **off** | 14.00s | 10.00s | 4.18s | 4.0 |

**-55% on the node.** Caching the query *results* would have saved nothing; the win came
from removing round trips. Guarded by `EAC_CATALOG_MAX_CHARS` so a large catalog falls
back to the SQL tools instead of inflating every prompt.

### 4b. Remove the double summarization (`runbook_agent`)

The ReAct sub-agent spent a second LLM call turning retrieved chunks into prose, which
`synthesize` then summarized again. Replaced with a query planner plus parallel search,
handing raw documents to synthesis.

| node | before | after |
|---|---|---|
| `runbook_agent` | 4.31s | **1.62s** |
| turn total (3-run mean) | 12.07s | **9.97s** (warm runs 7.9s) |
| TTFT | 8.06s | **6.59s** (warm 4.7s) |

### 4c. Preload recent incidents

Added after the eval showed briefs had silently stopped reporting incident history: once
the catalog removed the need for tool calls, the model stopped calling `query_incidents`
too. Snapshot grew 2192 → 4145 chars (~1036 tokens), still well inside the 12000 budget.

## 5. Cumulative results

### Latency

| measurement | baseline | final |
|---|---|---|
| eval p95 | 19.32s | **9.59s** (-50%) |
| eval p50 | 3.84s | 3.50s |
| live `/chat` average | 18.87s | **10.17s** (-46%) |
| local probe, warm total | ~18.4s | **~7.9s** |
| local probe, TTFT | 17.57s | **~4.7s** |

Live `node_latency` after the work, from a real server session:

```
general_agent           6.90s   <- now the slowest node; never optimized
synthesize              4.33s
structured_agent        3.76s
runbook_agent           2.47s
triage                  1.34s
prompt_injection_check  0.06s   <- confirms the 3.40s first reading was cold start
validate_input          0.04s
```

The two paths reconstruct to ~12.0s (incident) and ~8.3s (general), averaging 10.2s and
matching the reported 10.17s.

### Quality

Four full 103-example runs, LLM judges enabled. Run 2 graded 106 examples because of
the dataset bug in section 7, so its column is indicative only.

| evaluator | baseline | no-incid | +incid | +merge fix |
|---|---|---|---|---|
| `citation_validity` | 1.000 | 1.000 | 0.991 | **1.000** |
| `groundedness` | 0.733 | 0.716 | 0.726 | **0.745** |
| `keyword_coverage` | 0.892 | 0.898 | 0.900 | 0.905 |
| `appropriate_decline` | 0.864 | 0.882 | 0.875 | 0.885 |
| `retrieval_recall` | 0.918 | 0.920 | 0.918 | 0.900 |
| `routing_accuracy` | 0.924 | 0.926 | 0.913 | 0.913 |
| `retrieval_precision` | 0.443 | 0.431 | 0.400 | 0.395 |
| `factuality` | 0.903 | 0.869 | 0.876 | 0.856 |
| latency p95 | 19.32s | 10.93s | 10.54s | **9.59s** |

Concentrated in `multi-hop-incident`, the only category these changes touch:

| | baseline | no-incid | +incid | +merge fix |
|---|---|---|---|---|
| `groundedness` | 0.833 | 0.768 | 0.812 | **0.875** |
| `citation_validity` | 1.000 | 1.000 | 0.979 | **1.000** |
| `factuality` | 0.870 | 0.778 | 0.800 | 0.771 |

### Reading these deltas: the noise floor

Three post-change runs give a variance estimate the earlier single comparisons could not.
Incident `factuality` across them reads **0.778 / 0.800 / 0.771**, a spread of ~0.03. So:

- The incidents preload "recovering" factuality (0.778 → 0.800) was **noise**, and was
  over-read at the time.
- The merge fix "hurting" factuality (0.800 → 0.771) is **also noise**.
- The ~0.09 gap from baseline is roughly 3x that spread, so the regression is real and has
  been stable since the runbook refactor, unmoved by either subsequent fix.

`groundedness` on incidents climbed 0.768 → 0.812 → **0.875**, a monotonic 0.107 that sits
well outside the noise band and now exceeds the 0.833 baseline. `citation_validity`
returned to a clean 1.000. Those two are genuine wins.

Caveat: baseline is a single run, so its own variance is unknown. The true factuality gap
could be anywhere in ~0.06-0.12.

### Why grounding and factuality moved in opposite directions

Inspecting the run-4 failures showed the dominant pattern had *changed*. "Lacks specific
reference to RB-NNN" was no longer the leader; wrong dates and over-elaboration were:

```
judge: incorrectly dates the incident as October 10, 2024, instead of March 28, 2024
judge: includes additional, unverified details
judge: introduces additional details not present in the reference
```

Both are consequences of the changes here:

- **Wrong dates from the incidents snapshot.** The preloaded table hands the model 15
  rows of `started_at` values, a menu of plausible dates to pick the wrong one from.
  Before the preload it had to query for the specific incident.
- **Elaboration beyond the question.** `synthesize` reads raw chunks instead of a filtered
  summary, so it has more material and volunteers more. The judge scores the additions as
  unverified.

That resolves the apparent contradiction: the extra detail *is* traceable to retrieved
documents, which is why `groundedness` reached its best-ever value while `factuality` fell.
The answers are not ungrounded; they say more than was asked and misdate one fact.

## 6. What the failure inspection found

Reading the failing runs beat guessing at them. **6 of 8 factuality misses had *perfect*
groundedness**: answers that were true but missing the specific document.

```
fact=0.5 ground=1.0  "Stripe API key leaked"      judge: lacks specific reference to RB-015
fact=0.5 ground=1.0  "Tier-0 pods evicted on EKS" judge: lacks specific reference to RB-008
fact=0.5 ground=1.0  "notification-service Redis" judge: misses mentioning ADR-025
```

That pattern (grounded but incomplete) pointed at retrieval coverage, not hallucination,
and exposed two bugs in the new merge code:

1. **Query-major iteration.** With 3 queries x 3 blocks and a cap of 6, the third query
   contributed **nothing**. The planner is deliberately asked for complementary queries,
   so the discarded one often held the runbook. Fixed by interleaving by rank.
2. **Budget spent on duplicate documents.** One document supplies several chunks, so 6
   blocks carried only 3 distinct documents while the needed one was cut. Fixed with
   breadth before depth: one block per source first, leftovers for further chunks.

After both fixes, on the real corpus, the same three queries yield 4 distinct documents
instead of 3, and `015-emergency-secrets-rotation` (the `RB-015` the judge named) now
reaches synthesis. Re-running the 8 failing questions locally:

| outcome | count |
|---|---|
| expected document now retrieved | **5** |
| pre-existing routing failure | 2 |
| genuine retrieval breadth gap | 1 |

Run 4 confirmed these fixes on the judged metrics they were aimed at: incident
`groundedness` reached 0.875 (best of all runs, above baseline) and `citation_validity`
returned to 1.000. They did **not** move `factuality`, because by then the failure mode
had shifted to the two mechanisms described in section 5.

## 7. Bugs found in existing code

- **The eval dataset re-seed was corrupt.** Examples were deleted while iterating a lazily
  paginated generator, so pages were skipped and stale examples survived. One run graded
  106 examples against a 103-row golden set. Comparisons across that run are unreliable.
- **Triage misclassifies historical incident questions.** "What was the root cause when an
  EKS deploy wedged the cluster in October 2024?" routes to `out_of_scope` and is declined
  outright.
- **`general_agent` answers document questions with SQL.** "Which postmortem covers that?"
  produced three `query_incidents` calls, no doc search, and a denial that the incident
  existed.

The last two are independent of this work (`triage` runs first and never sees the
snapshot; `general_agent` does not receive it either) but they cost factuality points that
were initially misattributed to the refactor.

## 8. Mistakes worth recording

Three predictions were wrong, each caught by measurement rather than review:

1. **"Redundant embedding calls are the bottleneck."** Real cost: ~0.2s, and only on
   ADR-by-id queries. The supersession cache was already avoiding most of them.
2. **"The citation regression is `postmortem_id` confusion."** It was the catalog snapshot
   supplying facts with no `Cite as:` line, so the model invented attribution for them.
3. **"Tighten the block caps to cut noise."** The opposite: the caps were already deleting
   documents the answers needed. Tightening would have made it worse.

Two further notes:

- **Parallelizing the sub-agents lost most of its value mid-effort.** Fanning
  `structured_agent` and `runbook_agent` out from `triage` was worth ~5s at the start and
  ~1.6s after the catalog preload. Batching changes would have hidden that.
- **A prompt line still needs fixing.** The structured prompt calls the snapshot "the
  complete, authoritative list ... plus the most recent incidents" and instructs the model
  to say when a service has no prior incidents. "Complete" is false for a capped incident
  list, and the combination encourages the denial behaviour seen in section 7.

## 9. Open items

Three prompt fixes were applied after run 4 and verified by local probe, but are **not yet
covered by an eval run**:

| fix | before | after |
|---|---|---|
| `synthesize` answers the question and stops | ~2000 char brief | 1454 chars, tighter |
| Incident dates must come from a positively matched row | "October 10, 2024" | "March 28, 2024" (correct) |
| An empty SQL result is not proof something never happened | "no recorded incidents" | finds `2024-006-currency-rounding-incident-eu` |

The third was the interesting one: the denial case routes to `general_agent`, so fixing the
incident prompt could not reach it. The real cause was in the shared `_GROUNDING` block,
which told every agent to report empty SQL results without ever saying that SQL does not
contain postmortems. It now requires a document search before concluding something does not
exist. Side effect to watch: that turn issued 8 `query_incidents` calls before searching.

Still open:

| item | why |
|---|---|
| Re-run the eval | The three fixes above are probe-verified only |
| Fix triage `out_of_scope` misclassification | Declines legitimate incident questions outright; `routing_accuracy` on incidents sits at 0.815 |
| Render `node` progress events in the UI | TTFT is 8.29s of a 10.17s turn; the events are already on the wire and discarded |
| Extend the catalog preload to `general_agent` | Now the slowest node at 6.90s, same SQL tools, same discover-by-round-trip cost |
| Re-run baseline once for its variance | Baseline is a single run, so the size of the factuality gap is only known to ~±0.03 |
| Report token and cost totals | `summarize_results` emits zeros; the README claims cost is surfaced |

## 10. Reproducing

```bash
make serve                                   # then ask a few incident and general questions
curl -s localhost:8000/metrics/summary | python -m json.tool
make eval                                    # full 103-example run, needs LANGSMITH_API_KEY
```

`node_latency` is sorted slowest-average-first, so the top row names the current
bottleneck. Ignore `overall_latency` percentiles until the sample is large: they are
computed from all HTTP requests including static assets, and clamp to bucket edges at low
counts. That was the original misleading signal.
