# Exact study prompts

These files retain the study instruction wording. They contain no benchmark topic text.

| File | Meaning |
|---|---|
| common.txt | Task template with goal, request, depth, and strategy placeholders |
| goals.json | Exact task objective for each collection |
| S0.txt | Empty strategy block |
| S1.txt | Specific-clue search and verification |
| S2.txt | Exploration using encountered information |
| S3.txt | Terminology expansion for the same request |
| S4.txt | Repetition of the task objective |

scripts/workflow.py assembles the task input from downloaded topics and these files. S1–S3 include the original introduction and a leading newline; S4 repeats the corresponding task goal. TAR adds the six protocol fields in fixed order and the inclusive publication-date sentence.

The agent-level base prompt, tool schemas, checkpoint instruction, and repair text remain in python_search_agent/search_agent/. See [skill derivation](../docs/SKILL_DERIVATION.md) and [experiment setup](../docs/EXPERIMENT_SETUP.md).

At release preparation, assembled prompts were compared with all 1080 original topic-condition prompt texts. Full topic prompts are generated locally and are not committed.
