# Common Python search agent

The controller executes one independent search session using an externally supplied model deployment and a prepared local Lucene collection. The model receives the fixed task prompt and its assigned strategy, and can call search, open, and finish.

Use the repository's [experiment wrapper](../scripts/run_experiment.py) to select a task, topic, and S0–S4 condition and automatically score the result. Full setup instructions are in [RUNNING.md](../docs/RUNNING.md); exact study text and method details are in [EXPERIMENT_SETUP.md](../docs/EXPERIMENT_SETUP.md).

## Modules

| Module | Responsibility |
|---|---|
| loop.py | Explicit history, LiteLLM requests, tool calls, one repair, checkpoints |
| policy.py | Fixed role, tools, request validation, fresh request identity |
| gateway.py | Controller-owned credentials and bounded transport retry |
| sandbox.py | Bubblewrap isolation of the conversation loop |
| execution.py | Controller/loop communication and trajectory reconciliation |
| session.py | Search/open/finish state and final query selection |
| retrieval.py | Fixed Lucene/BM25 retrieval and rank fusion |
| __main__.py | One-session entry point |

Only the controller can read indexes and credentials. The model has no shell, browser, arbitrary code-execution, or delegation tool. Retrieved text is treated as evidence.

## Direct invocation

Run from this folder with the controller environment:

~~~bash
python -m search_agent \
  --prompt-file /data/prompts/tot2023/1006/S3.txt \
  --index /data/indexes/tot2023 --task tot2023 \
  --output /results/new-session \
  --deployment /private/model.local.json \
  --java-home /absolute/path/to/java-21 \
  --loop-venv /absolute/path/to/loop-venv
~~~

For TAR, add --publication-dates START END, using the topic's YYYYMMDD date range. The output folder must be new. A null or omitted session_seconds means no session time limit.

The direct entry point saves ranking.json and controller/loop records but does not run an official evaluator. Use [evaluate_run.py](../scripts/evaluate_run.py) afterward, or use the main wrapper from the outset.

The loop pins LiteLLM 1.105.0. Live endpoints must implement the Responses contract used by the code. Deployment examples are placeholders; configure and validate your chosen provider before collecting results.

## Tests

~~~bash
python -B -m unittest discover -s tests -p 'test_*.py' -v
~~~

Tests use synthetic responses and no API key. The optional sandbox fixture is described in [RUNNING.md](../docs/RUNNING.md).
