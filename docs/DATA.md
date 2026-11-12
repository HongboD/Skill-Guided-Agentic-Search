# External datasets and input formats

No benchmark corpus, original topic text, relevance judgments, index, or raw trajectory is distributed in this repository. Download these locally and keep them under data/ or another untracked location. The source sites' terms apply; the project's MIT license does not replace them.

## Official sources

| Task | What to obtain | Source |
|---|---|---|
| TREC Tip-of-the-Tongue 2023 | 2023 corpus.jsonl, 150 test topics, test qrels | [2023 track download table](https://trec-tot.github.io/guidelines-2023), [NIST test topics and judgments](https://trec.nist.gov/data/tot2023.html) |
| TREC Genomics 2007 | Original HTML archives, legalspans.txt, 2007topics.txt, original gold-standard judgment file | [Collection access and format](https://dmice.ohsu.edu/trec-gen/2007data.html), [2007 topics and gold standard](https://dmice.ohsu.edu/trec-gen/data/2007/), [NIST track page](https://trec.nist.gov/data/t2007_genomics.html) |
| CLEF TAR 2018 Task 1 | Testing topics, complete review protocols, publication date ranges, Task 1 content qrels | [Official 2018 release](https://github.com/CLEF-TAR/tar/tree/master/2018-TAR), [Task 1 description](https://github.com/CLEF-TAR/tar/tree/master/2018-TAR/Task1) |
| TAR document collection | Historical PubMed 2018 baseline, files pubmed18n0001.xml.gz through pubmed18n0928.xml.gz | [NLM download guidance](https://pubmed.ncbi.nlm.nih.gov/download/), [2018 naming documentation](https://www.nlm.nih.gov/pubs/techbull/nd17/nd17_medline_data_changes_2018.html) |

The current PubMed download directory is an annually refreshed baseline, not a guarantee that the 2018 snapshot is still hosted. Obtain an archived copy of the exact 2018 baseline through the dataset provider or an authorized archive. No currently working public URL for the complete historical snapshot was verified for this release. The preparer requires the 928 historical filenames and will reject an incomplete collection.

Use the **2023** ToT corpus from its original track page. Later ToT corpora contain different collections. The study's first-ID deduplication yields 231848 records; verify the prepared count rather than assuming that a similarly named download is the same snapshot.

Genomics requires the released legal byte spans over the original HTML. A newly extracted article collection is not equivalent. TAR Task 1 requires the full historical PubMed collection and content judgments, not the Task 2 candidate pools or abstract-screening judgments.

## Small metadata downloads

These commands download only public metadata into ignored local directories:

~~~bash
mkdir -p data/raw data/qrels
curl -fL https://trec.nist.gov/data/tot/2023-test.zip -o data/raw/tot2023-test.zip
curl -fL https://trec.nist.gov/data/tot/2023-qrels.txt -o data/qrels/tot2023.txt
curl -fL https://dmice.ohsu.edu/trec-gen/data/2007/2007topics.txt -o data/raw/2007topics.txt
curl -fL https://dmice.ohsu.edu/trec-gen/data/2007/trecgen2007.gold.standard.tsv.txt -o data/qrels/genomics2007-released.txt
git clone --depth 1 https://github.com/CLEF-TAR/tar.git data/raw/clef-tar
~~~

In the CLEF release, use 2018-TAR/Task1/Testing/qrels/qrel_content_task1. Keep downloaded judgment bytes intact, especially the Latin-1 Genomics release.

The repository does not automatically fetch the large corpora. Follow the provider links above and retain the original filenames and any checksums supplied by the provider.

## Normalize public topic inputs

All runners accept a UTF-8 JSON array. Each topic needs topic_id (a string), title (a string, possibly empty), and text (the original request). Extra answer, qrel, and expert-query fields are excluded by the importer.

Extract the ToT test ZIP using the standard archive utility or the included extractor, then pass its topic JSONL:

~~~bash
cd retrieval_baselines
../.venv-baselines/bin/python -m ir_baselines extract \
  --source ../data/raw/tot2023-test.zip --output ../data/raw/tot2023-test
cd ..
python scripts/import_topics.py --task tot2023 --format tot-jsonl \
  --input data/raw/tot2023-test/test.jsonl \
  --output data/topics/tot2023.json --study-subset
python scripts/import_topics.py --task genomics2007 --format genomics-text \
  --input data/raw/2007topics.txt \
  --output data/topics/genomics2007.json --study-subset
~~~

Use the actual JSONL filename inside the downloaded ToT archive if it differs. The Genomics importer reads the released <ID>question format. --study-subset requires the exact published topic IDs from configs/study.json and discards any additional topics.

For TAR, normalize the downloaded testing topics and review-protocol metadata to the following schema. Values below are synthetic placeholders, not study data:

~~~json
[
  {
    "topic_id": "SYNTHETIC",
    "title": "Synthetic review",
    "text": "Synthetic review objective.",
    "protocol": {
      "objective": "Synthetic protocol objective.",
      "type_of_study": "Synthetic design.",
      "participants": "Synthetic population.",
      "index_tests": "Synthetic tests.",
      "target_conditions": "Synthetic condition.",
      "reference_standards": "Synthetic reference."
    },
    "publication_date_range": ["20000101", "20011231"]
  }
]
~~~

Copy the original public text exactly; do not summarize or infer missing review criteria or dates. The importer validates this normalized JSON:

~~~bash
python scripts/import_topics.py --task tar2018_full --format json \
  --input data/raw/tar2018-topics-normalized.json \
  --output data/topics/tar2018_full.json --study-subset
~~~

The repository validates the normalized TAR schema; it does not parse every upstream protocol document format automatically. Public topic and protocol preparation must supply all six fields and the dates. Topic identifiers are included as experimental split configuration, while their text is downloaded externally.

## Prepare and index

See [retrieval_baselines/README.md](../retrieval_baselines/README.md) for corpus conversion and indexing commands. Expected prepared counts are 231848 ToT documents, 12641127 Genomics legal passages, and 27836723 PubMed citations. Counts help detect the wrong snapshot; matching counts alone do not establish byte identity.
