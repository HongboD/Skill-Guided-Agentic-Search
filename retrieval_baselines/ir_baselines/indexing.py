"""Build a new local Lucene index from public document records."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile

from .retrieval import DEFAULT_ANALYZER


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(path, value):
    path = Path(path)
    content = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_record(record):
    """Keep the full supplied public raw record, with strict required fields."""
    if not isinstance(record, dict) or set(record) != {"id", "title", "contents", "metadata"}:
        raise ValueError("index record requires exactly id, title, contents, metadata")
    if (not isinstance(record["id"], str) or not record["id"]
            or any(char.isspace() or char == "\x00" for char in record["id"])):
        raise ValueError("document ID must be non-empty text without whitespace or null characters")
    if not isinstance(record["title"], str) or not isinstance(record["contents"], str):
        raise ValueError("title and contents must be strings")
    if not isinstance(record["metadata"], dict):
        raise ValueError("metadata must be an object")
    publication_date = record["metadata"].get("publication_date")
    if publication_date is not None:
        if not isinstance(publication_date, str) or not re.fullmatch(r"[0-9]{8}", publication_date):
            raise ValueError("publication_date must use YYYYMMDD")
        try:
            datetime.strptime(publication_date, "%Y%m%d")
        except ValueError as error:
            raise ValueError("publication_date is not a calendar date") from error
    # Reject non-JSON data and non-finite values before passing to Java.
    json.dumps(record, ensure_ascii=False, allow_nan=False)
    return record


def validate_index_config(config):
    analyzer = dict(config.get("analyzer", DEFAULT_ANALYZER))
    if set(analyzer) != set(DEFAULT_ANALYZER):
        raise ValueError("analyzer requires language, stemming, stemmer, stopwords")
    fields = list(config.get("fields", ("contents", "title")))
    if not fields or len(set(fields)) != len(fields) or set(fields) - {"contents", "title"}:
        raise ValueError("invalid indexed text fields")
    bm25 = config.get("bm25")
    if not isinstance(bm25, dict) or set(bm25) != {"k1", "b"}:
        raise ValueError("BM25 requires explicit k1 and b")
    if (any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in bm25.values()) or bm25["k1"] <= 0 or not 0 <= bm25["b"] <= 1):
        raise ValueError("invalid BM25 parameters")
    return analyzer, fields, bm25


def build_index(records, index_path, config, *, provenance=None):
    """Build a fresh index. A failed build is marked and never reported ready.

    Caller owns storage placement. Existing directories are never overwritten.
    IDs are checked in a temporary SQLite B-tree to keep memory bounded on the
    full PubMed collection.
    """
    analyzer_config, fields, bm25 = validate_index_config(config)
    index_path = Path(index_path)
    if index_path.exists():
        raise FileExistsError("index target already exists; choose a new build directory")
    # Fail on missing dependencies before creating an apparent partial index.
    from pyserini.analysis import get_lucene_analyzer
    from pyserini.pyclass import autoclass
    from jnius import cast
    classes = {name: autoclass(path) for name, path in {
        "Paths": "java.nio.file.Paths", "FSDirectory": "org.apache.lucene.store.FSDirectory",
        "IndexWriter": "org.apache.lucene.index.IndexWriter",
        "IndexWriterConfig": "org.apache.lucene.index.IndexWriterConfig",
        "OpenMode": "org.apache.lucene.index.IndexWriterConfig$OpenMode",
        "DirectoryReader": "org.apache.lucene.index.DirectoryReader",
        "IndexOptions": "org.apache.lucene.index.IndexOptions",
        "Document": "org.apache.lucene.document.Document",
        "StringField": "org.apache.lucene.document.StringField",
        "StoredField": "org.apache.lucene.document.StoredField",
        "BinaryDocValuesField": "org.apache.lucene.document.BinaryDocValuesField",
        "Field": "org.apache.lucene.document.Field", "FieldType": "org.apache.lucene.document.FieldType",
        "TextField": "org.apache.lucene.document.TextField", "Store": "org.apache.lucene.document.Field$Store",
        "BytesRef": "org.apache.lucene.util.BytesRef",
        "BM25Similarity": "org.apache.lucene.search.similarities.BM25Similarity",
        "Version": "org.apache.lucene.util.Version", "System": "java.lang.System", "String": "java.lang.String",
    }.items()}
    index_path.mkdir(parents=True, exist_ok=False)
    marker = index_path / "search_v2_build.json"
    started = _now()
    _json(marker, {"status": "BUILDING", "started_at_utc": started})
    duplicate_db = index_path / "build_ids.sqlite"
    db = writer = reader = directory = analyzer = None
    count = dated = 0
    try:
        db = sqlite3.connect(duplicate_db)
        db.execute("CREATE TABLE ids (id TEXT PRIMARY KEY) WITHOUT ROWID")
        analyzer = get_lucene_analyzer(**analyzer_config)
        directory = classes["FSDirectory"].open(classes["Paths"].get(str(index_path)))
        writer_config = classes["IndexWriterConfig"](analyzer)
        writer_config.setOpenMode(classes["OpenMode"].CREATE)
        writer_config.setSimilarity(classes["BM25Similarity"](float(bm25["k1"]), float(bm25["b"])))
        writer = classes["IndexWriter"](directory, writer_config)
        text_type = classes["FieldType"](classes["TextField"].TYPE_NOT_STORED)
        text_type.setIndexOptions(classes["IndexOptions"].DOCS_AND_FREQS_AND_POSITIONS_AND_OFFSETS)
        text_type.setStoreTermVectors(True)
        text_type.setStoreTermVectorPositions(True)
        text_type.setStoreTermVectorOffsets(True)
        text_type.freeze()
        for record in records:
            validate_record(record)
            try:
                db.execute("INSERT INTO ids VALUES (?)", (record["id"],))
            except sqlite3.IntegrityError as error:
                raise ValueError("duplicate document ID: " + record["id"]) from error
            document = classes["Document"]()
            document.add(classes["StringField"]("id", record["id"], classes["Store"].YES))
            document.add(classes["BinaryDocValuesField"]("id", classes["BytesRef"](record["id"].encode('utf-8'))))
            document.add(classes["StoredField"]("raw", json.dumps(record, ensure_ascii=False, allow_nan=False)))
            for field in fields:
                document.add(classes["Field"](field,
                    cast('java.lang.CharSequence', classes['String'](record[field])),
                    cast('org.apache.lucene.index.IndexableFieldType', text_type)))
            publication_date = record["metadata"].get("publication_date")
            if publication_date is not None:
                document.add(classes["StringField"]("publication_date", publication_date, classes["Store"].YES))
                dated += 1
            writer.addDocument(document)
            count += 1
            if count % 10000 == 0:
                db.commit()
                _json(marker, {"status": "BUILDING", "started_at_utc": started,
                               "records_processed": count, "updated_at_utc": _now()})
        if count == 0:
            raise ValueError("cannot mark an empty corpus ready")
        db.commit()
        unique_count = db.execute("SELECT COUNT(*) FROM ids").fetchone()[0]
        writer.commit()
        reader = classes["DirectoryReader"].open(directory)
        lucene_count = int(reader.numDocs())
        if count != unique_count or count != lucene_count:
            raise RuntimeError("source, unique ID, and Lucene document counts disagree")
        reader.close()
        reader = None
        writer.close()
        writer = None
        directory.close()
        directory = None
        analyzer.close()
        analyzer = None
        db.close()
        db = None
        duplicate_db.unlink()
        metadata = {"status": "READY", "format": "search_v2_lucene_v1", "document_count": count,
                    "unique_document_count": unique_count, "lucene_document_count": lucene_count,
                    "documents_with_publication_date": dated, "analyzer": analyzer_config,
                    "fields": fields, "bm25": dict(bm25), "raw_json_stored": True,
                    "term_vectors": True, "positions": True, "tie_break": "document_id_lexical",
                    "pyserini_version": importlib.metadata.version("pyserini"),
                    "lucene_version": str(classes["Version"].LATEST.toString()),
                    "java_version": str(classes["System"].getProperty("java.version")),
                    "started_at_utc": started, "completed_at_utc": _now(), "provenance": provenance}
        # Only a successful committed and count-checked build gets this file.
        _json(marker, {"status": "COMPLETE", "document_count": count, "completed_at_utc": metadata["completed_at_utc"]})
        _json(index_path / "search_v2_index.json", metadata)
        return metadata
    except Exception as error:
        _json(marker, {"status": "FAILED", "started_at_utc": started, "ended_at_utc": _now(),
                       "records_processed": count, "error_type": type(error).__name__, "error": str(error)})
        raise
    finally:
        if reader is not None:
            reader.close()
        if writer is not None:
            writer.rollback()
        if directory is not None:
            directory.close()
        if analyzer is not None:
            analyzer.close()
        if db is not None:
            db.close()


def jsonl_records(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError("blank JSONL record at line " + str(number))
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError("invalid JSONL record at line " + str(number)) from error


def fixture_records():
    for ident, contents in (("a", "alpha beta"), ("b", "alpha gamma"), ("c", "beta delta")):
        yield {"id": ident, "title": ident, "contents": contents, "metadata": {}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--jsonl", type=Path)
    source.add_argument("--fixture", action="store_true")
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {
        "analyzer": DEFAULT_ANALYZER, "fields": ["contents", "title"], "bm25": {"k1": .9, "b": .4}}
    records = fixture_records() if args.fixture else jsonl_records(args.jsonl)
    result = build_index(records, args.index, config,
                         provenance={"fixture": args.fixture, "source": str(args.jsonl) if args.jsonl else None})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
