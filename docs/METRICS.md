# Metric definitions

## Cohort and units

A cell is one model, task, topic, and condition.
There are 3,240 cells: three models, 216 topics, and five conditions.
Each cell contributes one accepted session.
Task means give each topic equal weight.
Scores remain separate by task because the tasks have different goals and metrics.
Valid zero scores remain in every analysis.

## Official retrieval measures

| Task | Primary measure | Other exported official measures |
|---|---|---|
| ToT 2023 | NDCG@1000 | The complete requested `trec_eval` output. |
| Genomics 2007 | Aspect MAP | Document MAP, Passage MAP, and Passage2 MAP. |
| TAR 2018 Task 1 | Recall@5000 | Every topic measure printed by the released Task 1 scorer. |

NDCG is discounted cumulative gain divided by ideal discounted cumulative gain.
The bundled `trec_eval` defines gain, rank discount, and treatment of unjudged records.
For a single binary target at rank r, NDCG is `1/log2(r+1)`.
A missed target scores zero.

Genomics Aspect MAP measures precision as ranked passages retrieve the topic's relevant information aspects.
Its denominator comes from judged aspects, not the 1,000-position output cutoff.
The released scorer defines overlap using article IDs and original byte spans.
The four Genomics measures use that scorer's separate document, passage, aspect, and character calculations.
The full implementation is included, with its Python 3 compatibility diff.

For Aspect AP, the scorer walks the ranked passages and tracks aspects already found.
A passage with new aspects increases both precision counters by one.
Its contribution is the number of new aspects multiplied by the current precision.
A passage with only previously found aspects leaves the counters unchanged.
A passage with no relevant aspect increases only the precision denominator.
Divide the accumulated contribution by all judged unique aspects for that topic.
Aspect MAP is the mean of these topic values.

TAR Recall@5000 is the number of retrieved judged-relevant citations divided by the topic's relevant-citation count.
The official scorer treats judgment values 1 and 2 as relevant.
Its printed recall has three decimal places.
Primary comparisons use that printed value, matching the original evaluations.
Coverage diagnostics also retain exact fractions before rounding.
For an empty list, the package initializes and finalizes the official Task 1 ruler with no retrieved items.

`expected_evaluation.json` records the primary score and all topic scores for a cell.
`official_selected.json` independently recomputes them.
The verifier compares every exported primary and secondary metric.

The TAR secondary fields have the following meanings:

| Fields | Definition and implementation |
|---|---|
| `num_shown`, `rels_found`, `num_rels` | Evaluated records, retrieved relevant records, and relevant denominator. `CountBasedMeasures`. |
| `last_rel`, `norm_last_rel` | Last retrieved relevant rank and that rank divided by the scorer's document count. `CountBasedMeasures`. |
| `threshold`, `norm_threshold` | Screening threshold and its normalized value. The submitted Task 1 action field is zero. `CountBasedMeasures`. |
| `wss_100`, `wss_95` | Official work-saved diagnostics, zero when the required recall level is not reached. `CountBasedMeasures`. |
| `ap` | Sum of precision at each relevant rank, divided by the relevant denominator. `MAPBasedMeasures`. |
| `norm_area` | Normalized area under cumulative relevant-document gain. `AreaBasedMeasures`. |
| `total_cost` | The released evaluator's fixed utility-cost calculation. `UtilityBasedMeasure`. |
| `recall_total`, `recall_max` | Retrieved relevant count and relevant denominator. `RecallBasedMeasures`. |
| `recall_at_threshold`, `recall_threshold` | Recall at the screening threshold and its rank. `RecallBasedMeasures`. |
| `recall@k` | Recall at each printed cutoff from 50 to 5,000. `RecallBasedMeasures`. |

These classes are in `vendor/tar2018/measures/eval_measures_2018.py`.
`tar_rulers_2018.py` defines the exact Task 1 combination and constants.
The report uses Recall@5000 as its primary TAR measure.
Other printed fields are retained for verification at the released scorer's precision.

## Ranking and selection

Each query stores its ordered top 1,000 records, or top 5,000 for TAR.
The final output fuses the one to three query IDs chosen by `finish`.
For document d, `RRF(d) = sum(1 / (60 + rank_q(d)))` over contributing lists.
Ranks start at 1. Equal fusion scores use lexical document ID order.
The final cutoff is 1,000 for ToT and Genomics, and 5,000 for TAR.
Official run files use descending ordinal scores to preserve this order.

The all-query replay uses each distinct successful query text once.
It strips outer whitespace and keeps the first occurrence of each text.
It applies the same RRF rule and cutoff as the final selection.
It uses stored query lists, without running new retrieval.
The selected-list replay must exactly match both `ranking.json` and `run.trec`.

For TAR, k is the number of selected query IDs.
The first-k and last-k diagnostics fuse the first or last k distinct queries.
Pool coverage is the relevant-document share found in the union of all distinct-query lists.
The coverage gap is pool coverage minus exact recall of the selected final list.
The cumulative coverage points use `ceil(fraction * distinct_query_count)` at 25%, 50%, 75%, and 100%.
A query adds relevant material when it finds a judged-relevant ID absent from all earlier query lists.
All-condition intervals first average the five conditions within each topic, then resample topics.

## Action measures

The measurement function reads only the public task, actions, returned text, and response-batch order.
Model names, conditions, scores, and usage are joined after this calculation.

| Field | Definition |
|---|---|
| `search_attempts`, `open_attempts` | Executed calls, including calls that return a tool error. |
| `searches`, `open_successes` | Executed calls with an `ok: true` result. Paging is a search call. |
| `unique_query_texts` | Successful query strings after outer whitespace removal. |
| `unique_documents_seen` | Distinct IDs delivered in search pages. |
| `unique_parent_documents_seen` | Distinct publications in those pages for Genomics; ordinary IDs for other tasks. |
| `unique_documents_opened` | Distinct IDs opened successfully. |
| `docs_per_search` | Distinct parent documents opened divided by successful search calls. |
| `formulation_diversity` | Mean pairwise Jaccard distance between non-empty query term sets. |
| `lexical_evidence_adoption_rate` | Share of successful searches after the first with at least one newly adopted evidence term. |
| `zero_hit_rate` | Successful searches with no matches divided by successful searches. |
| `paging_rate` | Successful searches with positive offset divided by successful searches. |
| `repeated_query_rate` | `1 - unique_query_texts / searches`. |
| `selected_query_count` | Number of query IDs in the valid final `finish`. |
| `action_batches` | Number of model response batches containing recorded actions. |
| `searches_per_action_batch` | Successful searches divided by action batches. |

For term sets, decode HTML entities, apply Unicode NFKC, and convert to lowercase with `casefold`.
Extract Unicode letter and number tokens, excluding underscores.
Remove AND, OR, NOT, `contents`, and `title`.
For query terms, also remove field prefixes and numeric proximity or boost suffixes.
Jaccard distance is `1 - size(A intersection B) / size(A union B)`.
The diversity measure includes repeated and paging queries as separate successful calls.
It is null when fewer than two non-empty term sets exist.

An adopted term is absent from the original request and all earlier queries.
It must occur in a preview or opened text delivered in an earlier response batch.
Content returned within the same response batch cannot explain another call in that batch.
The adoption denominator is successful search calls minus one.
It is null for a one-search session.
This is a lexical measure of evidence use. Semantic strategy adherence needs separate labels.

Boolean, phrase, and proximity query counts use explicit syntax in the query text.
Tool error counts and rejected request counts are retained separately.
They describe actions inside accepted sessions.

## Token measures

Usage files contain provider-reported counters for the accepted session.
GPT and DeepSeek input counts include cached input. Uncached input equals input minus cached input.
Claude uncached input equals input plus cache-creation input. Cached input is cache-read input.
Total tokens equal uncached input plus cached input plus output.
These totals include context-summary requests when used.
Tokens measure reported effort; tokenizers and caching rules differ between providers.

## Statistical calculations

Primary contrasts pair each S1-S4 score with S0 on the same topic.
Confidence intervals use 10,000 paired-topic bootstrap samples and percentile bounds at 2.5% and 97.5%.
Two-sided sign randomization uses 100,000 samples for these topic sets.
The p-value is `(exceedances + 1) / (samples + 1)`.
The fixed seed is 20261029.
Holm adjustment covers the four S1-S4 versus S0 tests within each model and task.

Three exploratory families are also included:

1. The 27 S1-S3 versus S0 contrasts across models and tasks.
2. The 27 S1-S3 versus S4 contrasts across models and tasks.
3. The 27 paired differences in skill effects across model pairs, tasks, and S1-S3.

Each family has its own Holm adjustment.
Behavior and replay intervals use 10,000 paired-topic samples, seed 20261106, without multiplicity adjustment.
They describe associations and selection diagnostics.
Ratios divide condition means by baseline means over the same valid topic pairs.
Null behavior values are excluded pairwise and their sample count is reported.
Wins and losses use a tolerance of `1e-10`; differences within that tolerance are ties.
Leave-one-topic-out ranges show how the mean effect changes when each topic is removed in turn.

`analysis.json` contains mean scores, paired effects, intervals, adjusted p-values, and quality-effort counts.
`diagnostics.json` contains selection replay, coverage, topic distributions, and case evidence.
Case topics are selected by the largest observed DeepSeek S2 TAR gain and loss.
They explain concrete actions; they are not an independent sample.
