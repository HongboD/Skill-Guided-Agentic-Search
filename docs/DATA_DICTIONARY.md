# Result and run schemas

## Published results

metrics.json contains one row for every accepted model/task/topic/condition cell. The identity fields are model, job_id, task, topic_id, and condition. primary_score is the official task metric. Other fields describe action counts, evidence-use measures, final query selection, and provider-reported token usage. Null measures indicate an undefined denominator or unavailable observation.

analysis.json contains means, paired contrasts, confidence intervals, adjusted p values, and exploratory model comparisons. diagnostics.json contains aggregate selection and coverage summaries. all_queries_scores.json uses setup as its model label and stores primary_score, all_query_score, and score_difference.

tar_replay_summary.json has 450 TAR cell records, selected/first-k/last-k/all-query scores, relevant-pool coverage, and cumulative coverage fractions. Raw query text and per-query diagnostics are excluded.

official_baselines.json contains 432 baseline evaluations. B0 is BM25; B1 is BM25+RM3. paper_tables.md and paper_plot_data.json present these numerical results.

## Fresh runs

The wrapper writes experiment.json with the task, topic, condition, model identifier, duration policy, and TAR date range. The agent's ranking.json is an array of doc_id, rank, and score records. The official run file uses descending ordinal scores to preserve that computed order.

For Genomics, doc_id is PMID:byte_offset:byte_length and the official run uses seven columns. ToT and TAR use six-column run files. The evaluator's scores.json contains task, per-topic metrics, primary scores, and mean_primary_score.

query_results/ stores every successful retrieval ranking; session and model records retain tool deliveries and conversation events. These generated records are local outputs and are ignored by Git.

## External archived cohort

The lower-level legacy analysis expects the [saved-record layout](ANALYSIS.md). Its manifest joins evaluations with neutral action records. It does not obtain benchmark inputs from this public repository.

See [METRICS.md](METRICS.md) for formulas, denominators, rounding, and statistical families.
