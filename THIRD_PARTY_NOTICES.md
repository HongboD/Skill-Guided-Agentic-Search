# Third-party notices

The MIT license at the repository root covers original project code and documentation. It does not override upstream notices or confer rights to separately downloaded datasets.

## Official evaluation code

- retrieval_baselines/vendor/trec_eval/: [NIST trec_eval](https://github.com/usnistgov/trec_eval), study source version 9.0.7. Existing Chris Buckley copyright and permission notices remain in the source files. The bundled legacy headers specify permission for research, non-commercial purposes; this component is excluded from the project's MIT grant.
- retrieval_baselines/vendor/genomics2007/: [released Genomics 2007 scorer](https://dmice.ohsu.edu/trec-gen/data/2007/). The original Python 2 source, Python 3 compatibility port, and compatibility diff are included. Upstream comments and attribution remain unchanged.
- retrieval_baselines/vendor/tar2018/: [CLEF TAR scorer source](https://github.com/CLEF-TAR/tar). Original author labels and source comments remain unchanged.

Available upstream notices are preserved. Files without an explicit upstream license grant are not relabeled as MIT. Consult the source distributor for uses beyond the permissions accompanying that source.

No compiled scorer executable is tracked. Build trec_eval from the included source.

## Dependencies and literature

Pyserini, Lucene/Anserini, LiteLLM, NumPy, PyJNIus, and Bubblewrap are external dependencies with their own terms. Their code is installed separately.

Research strategy citations appear in docs/SKILL_DERIVATION.md. Publisher PDFs are not redistributed. Names in third-party notices and literature references are attribution to those sources; they are not project-author metadata.

## Benchmark material

Download the benchmark inputs from [their official sources](docs/DATA.md). No corpus, topic text, relevance judgments, prepared index, or raw document trace is included in this release.
