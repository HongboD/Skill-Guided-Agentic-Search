# Official scoring

The source implementations are included under retrieval_baselines/vendor/; benchmark judgments must be supplied externally.

| Task | Scorer and primary metric | Source |
|---|---|---|
| ToT 2023 | trec_eval 9.0.7, ndcg_cut.1000 | [NIST trec_eval](https://github.com/usnistgov/trec_eval) |
| Genomics 2007 | Released scorer, Aspect MAP | [OHSU release](https://dmice.ohsu.edu/trec-gen/data/2007/) |
| TAR 2018 Task 1 | Official tar_eval_2018.py, recall@5000 | [CLEF TAR release](https://github.com/CLEF-TAR/tar/tree/master/2018-TAR) |

The Genomics Python 3 compatibility diff is retained beside its original source. The evaluator uses original released judgment bytes. The TAR runner removes blank judgment lines in a temporary evaluation copy. Empty result lists are assigned the corresponding defined official score.

Run serialization preserves the computed ranking with decreasing ordinal scores. Genomics retains the original article/byte-span coordinates. Dataset judgments are used only after retrieval.

Upstream source notices remain intact; see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
