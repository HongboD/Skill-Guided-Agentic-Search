# Published numerical results

The reference cohort contains 3240 accepted sessions: 150 ToT, 36 Genomics, and 30 TAR topics, each under S0–S4 with three model backends. Baseline results contain 432 cells.

| File | Contents |
|---|---|
| paper_tables.md | Main score, contrast, coverage, and fixed-baseline tables |
| metrics.json | 3240 per-session scores, action measurements, and token counters |
| analysis.json | Paired tests, intervals, Holm adjustments, and model comparisons |
| diagnostics.json | Aggregate retrieval-pool and final-selection diagnostics |
| all_queries_scores.json | Selected versus all-query replay scores |
| tar_replay_summary.json | 450 TAR cells with numerical selection/coverage results |
| official_baselines.json | 432 primary/secondary baseline evaluation records |
| paper_plot_data.json | Numerical sources for figures |
| analysis_definition.json | Statistical settings |

These are result records, not benchmark input datasets. Original requests, qrels, document text, raw rankings, query histories, and full trajectories are excluded. Raw case-query details were removed from the public diagnostic summaries; the remaining numerical results are preserved.

Run analysis/reproduce.py to recompute the statistical analyses from these per-session measurements. Its verification explicitly distinguishes statistical recomputation from rescoring raw rankings and remeasuring behavior. Repeating the original model sessions requires the external benchmark data and compatible model deployments.

The measurement, official evaluation, and saved-ranking replay implementations are retained in analysis/ for externally supplied run exports; see [ANALYSIS.md](../docs/ANALYSIS.md). Result records use the original provider-reported token accounting. They do not estimate monetary cost or repeated-run variability.
