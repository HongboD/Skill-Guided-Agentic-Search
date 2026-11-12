# Contributing

Open an issue with a minimal synthetic example, the Python/dependency versions, and the command that failed. Avoid attaching API keys, provider credentials, private paths, benchmark documents, or full model transcripts.

Keep changes to retrieval, prompt wording, ranking, and scoring explicit: these can change the experimental method. Preserve reference results and add a focused test for behavior changes. Run:

~~~bash
python -B scripts/check.py
python -B scripts/check_release.py
~~~

If analysis code changes, also rerun analysis/reproduce.py into a new output directory and explain any numerical differences. Third-party scorer changes must preserve their attribution and be documented separately.

During anonymous review, use an anonymous contribution identity and review commit metadata before publishing.
