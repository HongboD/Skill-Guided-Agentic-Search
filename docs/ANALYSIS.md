# Statistical recomputation and raw-record analysis

## Published measurements

The dataset-free workflow is:

~~~bash
python -B analysis/reproduce.py --output runs/recomputed
~~~

It copies published per-session measurements into a new output directory, recalculates analysis.json and the aggregate diagnostics, regenerates the tables, and compares them with the reference results. It requires NumPy 2.4.3 but no corpus, qrels, index, model key, or raw trajectory.

The verification report explicitly records that official scores, raw behavior, and rankings were **not** recomputed in this mode. Their published measurements are the inputs. Raw query case examples are excluded from the public diagnostics.

## External saved-record exports

The lower-level original analysis programs remain available for a locally supplied saved-record export. Set SEARCH_REPRO_DATA to its root and SEARCH_REPRO_OUTPUT to a new output directory. The expected external layout has:

- manifest.json with model, model_folder, job_id, task, topic_id, condition, session, and trace fields.
- baseline_manifest.json with task, topic_id, condition, and session fields.
- data/qrels/<task>/qrels.txt; Genomics additionally uses released_qrels.txt.
- Per-session directories containing ranking.json, run.trec, queries.jsonl, selection.json, usage.json, and expected_evaluation.json.
- Neutral trace directories containing actions.jsonl, observations.jsonl, batches.jsonl, timeline.jsonl, task.txt, and validation.json.

Manifest paths are resolved relative to the external export. Neutral traces omit model/condition/outcome labels during measurement. The original measure.py and replay.py cache per-session outputs; use a fresh output directory after modifying code or data.

Run evaluate.py, measure.py, replay.py, evaluate.py --variant all, and evaluate.py --variant baselines in that order before analyze.py, summarize.py, and tables.py. The saved-cohort evaluators compare against expected score records and target the original 3240/432-cell cohort. They are not the entry point for scoring a new individual run.

Fresh agent sessions use scripts/evaluate_run.py. Converting new raw trajectories into the legacy neutral-export schema is a separate data-processing step; the public statistical workflow consumes the included numerical measurements.

## Interpretation

One accepted observation per model/topic/condition does not quantify repeated-run variability. Planned comparisons use within-model/task Holm families. Broader contrasts and behavior diagnostics are exploratory. Lexical evidence adoption measures term reuse, not semantic adherence. Offline query-selection replays do not constitute fresh model interventions.

See [METRICS.md](METRICS.md) for the definitions, denominators, seeds, and tolerances.
