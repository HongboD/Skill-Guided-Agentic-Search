# Running independent experiments

Run commands from the repository root unless a command explicitly changes directory. Supported tasks are tot2023, genomics2007, and tar2018_full; supported conditions are S0–S4.

## Environments

Live search uses Linux or WSL, Python 3.12, Java 21, Bubblewrap, and a C compiler/Make for trec_eval. Provide sufficient disk space for the original corpora and indexes. Portable tests and statistical analysis also run on Windows.

Keep the original dependency pins in separate environments: the controller uses NumPy 2.4.3, while the baseline preparation environment uses NumPy 2.5.4. The loop contains the pinned LiteLLM dependency.

~~~bash
python3.12 -m venv .venv-controller
.venv-controller/bin/python -m pip install -r python_search_agent/requirements-controller.txt
python3.12 -m venv .venv-loop
.venv-loop/bin/python -m pip install -r python_search_agent/requirements-loop.txt
python3.12 -m venv .venv-baselines
.venv-baselines/bin/python -m pip install -r retrieval_baselines/requirements.txt
make -C retrieval_baselines/vendor/trec_eval trec_eval
~~~

For statistics alone, install requirements-analysis.txt in .venv-analysis. The study's full dependency environments are not installed by the portable tests.

## Model configuration

Copy configs/deployment.example.json to configs/model.local.json. Fill in the deployment's model identifier and HTTPS endpoint. The endpoint must implement the Responses contract expected by the pinned loop: streaming, complete response events, function calls, and explicit history. A model name alone does not establish provider compatibility; a provider exposing a different API needs a validated adapter.

Set SEARCH_API_KEY in the controller's environment using your secret-management workflow. Keys never belong in a deployment file, prompt, commit, or issue. The sample endpoint is deliberately a placeholder.

Retain the common settings: no session time limit; xhigh requested reasoning; a context checkpoint threshold of 245480 estimated tokens; the same three tools. Provider-specific token accounting is retained as reported.

## Prepare topics and indexes

Follow [DATA.md](DATA.md) to download the exact benchmark edition and normalize its topics. Follow [the retrieval guide](../retrieval_baselines/README.md) to prepare and index the collection. The index builder emits search_v2_index.json; the controller verifies the format, analyzer, fields, and BM25 settings.

To materialize all five condition prompts for a task locally:

~~~bash
python scripts/build_prompts.py --task tot2023 \
  --topics data/topics/tot2023.json --output data/prompts/tot2023
~~~

The experiment wrapper assembles the same text automatically. Full topic prompts are intentionally not tracked.

## Run one cell

~~~bash
.venv-controller/bin/python scripts/run_experiment.py \
  --task genomics2007 --topic 200 --condition S1 \
  --topics data/topics/genomics2007.json \
  --index /data/indexes/genomics2007 \
  --deployment configs/model.local.json \
  --java-home /absolute/path/to/java-21 \
  --loop-venv .venv-loop \
  --qrels data/qrels/genomics2007-released.txt \
  --output runs/genomics2007-200-S1
~~~

For TAR, use --task tar2018_full and its topic ID, normalized topics, historical index, and Task 1 content judgments. The wrapper passes the topic's inclusive publication date range to the controller. No scheduler, queue service, or desktop notifier is required. Each output path must be new, so reruns cannot overwrite an earlier observation.

Use --dry-run to inspect the assembled input without creating a run or contacting a model. If intentionally collecting an unevaluated run, use --skip-evaluation; the result is not yet an officially evaluated observation.

A successful run contains prompt.txt, experiment.json, settings.json, result.json, ranking.json, query_results/, and complete controller/loop records. With evaluation enabled it also contains evaluation/run.trec and evaluation/scores/scores.json. A controller PASS alone is distinct from an official evaluation.

## Evaluate an existing output

~~~bash
.venv-controller/bin/python scripts/evaluate_run.py \
  --task genomics2007 --topic 200 \
  --ranking runs/genomics2007-200-S1/ranking.json \
  --qrels data/qrels/genomics2007-released.txt \
  --output runs/genomics2007-200-S1-rescore
~~~

This uses the original released Genomics judgment bytes. ToT uses NDCG@1000; Genomics uses Aspect MAP; TAR uses Recall@5000. Scores are calculated after search and are never shown to the model.

## Live synthetic fixtures

These checks require prepared dependency environments, but no model API:

~~~bash
cd retrieval_baselines
PYTHONPATH=. ../.venv-baselines/bin/python -B tests/live_fixture.py
cd ../python_search_agent
../.venv-controller/bin/python -B tests/sandbox_fixture.py \
  --venv ../.venv-loop --output ../runs/sandbox-fixture
~~~

The Lucene fixture builds a tiny synthetic index and tests BM25/RM3 date filters. The sandbox fixture checks SDK transport and context handling with local synthetic responses.

## Reproducibility limits

The published cohort has one accepted session per cell. Fresh stochastic model runs are not expected to reproduce every original trajectory or score. Preserve the recorded settings and report any provider, corpus, dependency, or protocol changes. The released code uses no global session time limit.
