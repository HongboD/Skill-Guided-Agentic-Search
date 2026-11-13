# Skill-Guided Agentic Search

Code, exact strategy prompts, and numerical results for studying how search instructions change retrieval quality and search behavior.

The study compares five conditions on three tasks and three model backends: **3,240 accepted sessions** (216 topics × 5 conditions × 3 models), plus **432 BM25/BM25+RM3 baseline runs**. The common Python agent exposes only search, open, and finish. Each cell runs independently; no scheduler is required.

**Benchmark datasets are not included.** Corpora, topic text, relevance judgments, indexes, full prompts containing topic text, and raw trajectories belong in local, ignored directories. [Download sources and input formats](docs/DATA.md) explain where to obtain them. The repository includes the study's numerical result summaries and per-session measurements.

## Start here

| Goal | Instructions |
|---|---|
| Inspect the findings | [Result tables](results/paper_tables.md), [findings](docs/FINDINGS.md), [result scope](results/README.md) |
| Recompute statistical tables without datasets or an API | Commands below |
| Run a new model/task/topic/condition cell | [Experiment guide](docs/RUNNING.md) |
| Prepare a collection, build an index, or run lexical baselines | [Retrieval guide](retrieval_baselines/README.md) |
| Inspect exact S0–S4 wording | [Prompt files](prompts/README.md), [method](docs/EXPERIMENT_SETUP.md) |
| Check release scope and anonymity | [Release notes](docs/ANONYMITY.md) |

## Recompute the published analysis

Python 3.12 and NumPy 2.4.3 are the reference analysis environment. Run from the repository root:

~~~bash
python3.12 -m venv .venv-analysis
.venv-analysis/bin/python -m pip install -r requirements-analysis.txt
.venv-analysis/bin/python -B analysis/reproduce.py --output runs/recomputed
~~~

This recalculates paired tests, intervals, corrections, diagnostics, and tables from the published per-session measurements. It compares the outputs with the reference results and writes runs/recomputed/VERIFICATION.json. It does **not** remeasure raw traces or rescore document rankings. Each output directory must be new. On Windows, use the environment's Scripts/python.exe instead of bin/python.

## Run a new experiment

Install the controller and loop environments following [RUNNING.md](docs/RUNNING.md), download a benchmark, normalize its topics, and prepare its index. Then:

~~~bash
.venv-controller/bin/python scripts/run_experiment.py \
  --task tot2023 --topic 1006 --condition S3 \
  --topics data/topics/tot2023.json \
  --index /data/indexes/tot2023 \
  --deployment configs/model.local.json \
  --java-home /absolute/path/to/java-21 \
  --loop-venv .venv-loop \
  --qrels data/qrels/tot2023.txt \
  --output runs/tot2023-1006-S3
~~~

Change the task, topic, condition, and deployment to select another cell. TAR publication dates are read from the topic metadata. The wrapper constructs the prompt, runs the agent, converts its ranking to the official format, and evaluates it. Add --dry-run to inspect the prompt without making a model call.

## Conditions

| Condition | Added instruction |
|---|---|
| S0 | No strategy block |
| S1 | Specific clues, controlled refinement, and verification |
| S2 | Follow information encountered while searching |
| S3 | Expand terminology for the same information need |
| S4 | Repeat the task objective |

## Project layout

- python_search_agent/: common agent, controller, sandbox, and synthetic tests.
- retrieval_baselines/: corpus preparation, Lucene indexing, BM25/RM3, and official scorer sources.
- scripts/: topic normalization, prompt construction, independent experiment execution, evaluation, and checks.
- prompts/: exact task template, task goals, and condition texts.
- analysis/: statistical analysis, behavior measurement, and saved-ranking evaluation/replay code.
- results/: published numerical results; no source documents or raw trajectories.
- configs/: shared settings and topic identifiers defining the experimental cohort.
- Trajectory/: examples of the experiment run trajectory, full data will be released upon paper acceptance

## Tests

~~~bash
python -B scripts/check.py
python -B scripts/check_release.py
~~~

Tests use synthetic inputs and make no model calls. Full retrieval and sandbox fixtures require the Linux/WSL dependencies described in [RUNNING.md](docs/RUNNING.md).

## License and citation

Original project code and documentation use the [MIT License](LICENSE). Third-party scorers retain their [upstream notices](THIRD_PARTY_NOTICES.md); datasets are downloaded separately under their original terms. Numerical results may be reused with attribution to this software and, when available, its associated paper.

This is an anonymous review release. [CITATION.cff](CITATION.cff) intentionally contains no author identity, institution, DOI, or identifying repository URL.
