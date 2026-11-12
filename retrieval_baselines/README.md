# Corpus preparation and lexical baselines

This package converts externally downloaded corpora, builds compatible Lucene indexes, and generates fresh BM25 and BM25+RM3 runs. No benchmark data is bundled. Get the inputs from [DATA.md](../docs/DATA.md).

Install requirements.txt in its own Python 3.12 environment; see [RUNNING.md](../docs/RUNNING.md). These commands run from retrieval_baselines/ with that environment active. Set JAVA_HOME to Java 21.

## Prepare local collections

~~~bash
python -m ir_baselines prepare --kind tot-raw \
  --source /data/tot2023/corpus.jsonl --output /data/prepared/tot2023

python -m ir_baselines prepare --kind genomics-html \
  --source /data/genomics/html --spans /data/genomics/legalspans.txt \
  --output /data/prepared/genomics2007

python -m ir_baselines prepare --kind pubmed2018 \
  --source /data/pubmed-baseline-2018 --output /data/prepared/tar2018_full
~~~

ToT keeps the first occurrence of each document ID and logs duplicates. Genomics slices the original HTML bytes at the released offsets, then decodes and cleans the passage. PubMed requires the full 928-file 2018 baseline, retains the highest PMID version, and records usable publication dates. The PubMed preparation makes two passes and requires substantial time and space.

Existing prepared TSVs are also supported with --kind tot-tsv and --kind genomics-tsv. ZIP archives can be extracted with:

~~~bash
python -m ir_baselines extract --source /data/source.zip --output /data/extracted/source
~~~

Use separate extraction subdirectories for Genomics journal archives. All output directories must be new.

## Build indexes

~~~bash
python -m ir_baselines index --jsonl /data/prepared/tot2023/corpus.jsonl \
  --output /data/indexes/tot2023 --expected-count 231848
python -m ir_baselines index --jsonl /data/prepared/genomics2007/corpus.jsonl \
  --output /data/indexes/genomics2007 --expected-count 12641127
python -m ir_baselines index --jsonl /data/prepared/tar2018_full/corpus.jsonl \
  --output /data/indexes/tar2018_full --expected-count 27836723
~~~

The record schema is id, title, contents, and metadata. The index stores raw JSON, positions, offsets, term vectors, and publication dates. The builder checks duplicate IDs and source/Lucene counts. Its search_v2_lucene_v1 metadata is accepted by the agent controller.

The fixed analyzer uses English stopwords and Porter stemming. BM25 uses k1=0.9 and b=0.4. RM3 uses 10 feedback documents, 10 terms, original-query weight 0.5, and term filtering. TAR date limits apply to feedback retrieval and final ranking.

## Run and evaluate baselines

Supply externally normalized topics and released judgments explicitly:

~~~bash
python -m ir_baselines run --task tot2023 --index /data/indexes/tot2023 \
  --topics /data/topics/tot2023.json --qrels /data/qrels/tot2023.txt \
  --method both --output /results/tot2023-baselines --evaluate

python -m ir_baselines run --task genomics2007 --index /data/indexes/genomics2007 \
  --topics /data/topics/genomics2007.json --qrels /data/qrels/genomics2007-released.txt \
  --method both --output /results/genomics2007-baselines --evaluate

python -m ir_baselines run --task tar2018_full --index /data/indexes/tar2018_full \
  --topics /data/topics/tar2018_full.json --qrels /data/qrels/tar2018-task1.txt \
  --method both --output /results/tar2018-baselines --evaluate
~~~

All three commands produce 432 rankings for the study cohort. Use --method bm25 or --method rm3 for one method; repeated --topic options select an explicit subset. Each topic records its input query, parsed query, ranking, and official run file. RM3 also records feedback document IDs and terms.

To evaluate an existing run, use the same selected topics:

~~~bash
python -m ir_baselines evaluate --task tot2023 \
  --topics /data/topics/tot2023.json --qrels /data/qrels/tot2023.txt \
  --run /results/tot2023-baselines/bm25/run.trec --output /results/tot2023-rescore
~~~

The bundled scorer sources retain upstream attribution. Build trec_eval with Make and a C compiler; evaluation builds it automatically if absent. Genomics consumes the original released judgment bytes.

## Checks

~~~bash
python -B -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=. python -B tests/live_fixture.py
~~~

The first command uses synthetic inputs. The second builds a tiny real Lucene index and checks BM25/RM3 date filtering.
