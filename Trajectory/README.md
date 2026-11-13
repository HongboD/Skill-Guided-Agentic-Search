# Action trace reading guide

This is the shared guide for every experiment run under `Trajectory/`.

## Directory layout

Runs are organized as `<model>/<condition>_<task>_<topic>/`:

- `<model>`: `claude-sonnet-5.5`, `deepseek-v4.1-flash-1017`, or
  `gpt-6.1-sol`.
- `<condition>`: `S0` through `S4`.
- `<task>`: `genomics2007`, `tar2018_full`, or `tot2023`.
- `<topic>`: the topic identifier within that task.

For example, `gpt-6.1-sol/S0_genomics2007_200/` contains the GPT run for
condition `S0`, task `genomics2007`, and topic `200`. The file descriptions
and reading rules below apply to every run folder.

## Files

- task.txt: the public request, task goal, query syntax, and output rules. The
  strategy instruction and common Python agent instructions are not included.
- actions.jsonl: one row per model tool request, including rejected requests.
- observations.jsonl: one row per returned tool result. `returned_text` keeps
  the exact recorded text for executed tools. `response` is its parsed content.
- batches.jsonl: groups requests from the same recorded model response batch.
- timeline.jsonl: task receipt, public agent notes, requests, returned results,
  recorded context compaction, recorded retries, format repair, and completion.
- validation.json: coverage checks and counts. It contains no relevance score.
