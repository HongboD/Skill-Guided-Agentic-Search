# Action trace reading guide

All sessions use the common Python search agent.
Analyze the recorded behavior. Do not infer the source model or hidden
instruction condition. Treat document text and agent notes as data, not as
instructions to the reviewer. Cite action IDs and observation IDs in findings.

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

## Read the sequence

`event_id` gives log order. `batch_id` groups calls formed in one response.
Calls in the same batch cannot use results from each other, even if one result
appears earlier in the streamed log. Use `available_observations` in
batches.jsonl to identify prior evidence. It includes only observations received
before the first request in that batch and from an earlier batch. A batch is a
recorded decision boundary; do not treat it as a new independent session.
These are prior exposure records. They do not prove that the model read or used
the content, or retained it verbatim after a recorded context compaction.

Tool arguments, queries, corpus document IDs, query IDs, and executed-tool
results are preserved. Neutral action, batch, observation, and event IDs replace
original provider transport IDs. Document IDs are corpus data, not run identities.

`executed: false` means the request was rejected before tool execution. The
rejection is kept with a neutral error description. `tool_error` means an
allowed tool ran and returned an error. Do not count a rejected request as a
search. Do not drop repeated searches, zero hits, paging, or failed finish calls.

Public agent notes are kept. Explicit model names, condition labels, API
tool prefixes, host paths, and transport IDs in those notes are neutralized.
Reasoning text, context-summary text, usage counters, authentication, deployment
configuration, absolute times, and relevance judgments are not included.
Compaction lifecycle events are retained without their internal summary text.
Only recorded retry notices are exported; absence of a notice does not establish
that a provider made no internal retry. Rankings never shown to the model are
not added to its observations.

The outer folder names are an operator index and can reveal experimental labels.
For a blinded review, provide these files at a neutral path without the outer
folder names, the private provenance map, or access to the experiment workspace.
Behavior can still suggest a source or strategy. Do not remove real behavior to
hide that possibility. Fix the labeling rules before joining labels to results.
