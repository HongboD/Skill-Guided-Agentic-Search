"""Prepare public corpora without modifying source files."""
import json
from pathlib import Path
from .text_records import iter_tot_records, iter_genomics_records, plain_html


def field(value):
    """Replace only TSV separators and null bytes with spaces."""
    return str(value or '').translate(str.maketrans({'\t': ' ', '\r': ' ', '\n': ' ', '\x00': ' '}))


def tot_records(source, duplicates):
    """Keep the first ID in JSONL order and log every omitted occurrence."""
    seen = set()
    with Path(source).open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            row = json.loads(line)
            ident = row['doc_id']
            if not isinstance(ident, str) or not ident or any(c.isspace() for c in ident):
                raise ValueError('Invalid document ID at line ' + str(number))
            if ident in seen:
                duplicates.write(json.dumps({'source_line': number, 'doc_id': ident,
                                              'record': row}, ensure_ascii=False) + '\n')
                continue
            seen.add(ident)
            title, body = field(row['page_title']), field(row['text'])
            yield {'id': ident, 'title': title, 'contents': title + '\n' + body,
                   'metadata': {'doc_id': ident}}


def genomics_records(html_root, spans):
    """Read legal byte slices before Latin-1 decoding and HTML normalization."""
    paths = {}
    for path in sorted(Path(html_root).rglob('*')):
        if path.is_file() and path.suffix.lower() == '.html':
            if path.stem in paths:
                raise ValueError('Duplicate HTML document ID: ' + path.stem)
            paths[path.stem] = path
    current, data = None, None
    with Path(spans).open(encoding='ascii') as stream:
        for line in stream:
            pmid, start, size = line.split()
            start, size = int(start), int(size)
            if current != pmid:
                data = paths[pmid].read_bytes()
                current = pmid
            if not pmid.isdigit() or start < 0 or size <= 0 or start + size > len(data):
                raise ValueError('Invalid legal span: ' + line.strip())
            contents = plain_html(field(data[start:start + size].decode('latin-1')))
            yield {'id': f'{pmid}:{start}:{size}', 'title': '', 'contents': contents,
                   'metadata': {'doc_id': pmid, 'pmid': pmid, 'offset': start, 'length': size}}


def prepare(kind, source, output, spans=None):
    """Write JSONL, omission logs, and a completion record to a new directory."""
    from contextlib import ExitStack
    from .indexing import validate_record, _json
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    count = 0
    with ExitStack() as stack:
        if kind == 'tot-raw':
            log = stack.enter_context((output / 'duplicates.jsonl').open('w', encoding='utf-8'))
            records = tot_records(source, log)
        elif kind == 'tot-tsv':
            records = iter_tot_records(source)
        elif kind == 'genomics-tsv':
            records = iter_genomics_records(source)
        elif kind == 'genomics-html':
            if spans is None:
                raise ValueError('--spans is required for genomics-html.')
            records = genomics_records(source, spans)
        elif kind == 'pubmed2018':
            from .pubmed import pubmed_files, iter_pubmed_records
            from .pubmed_versions import scan_versions
            selection = scan_versions(pubmed_files(source), output / 'version_selection.json')
            log = stack.enter_context((output / 'omitted_versions.jsonl').open('w', encoding='utf-8'))
            records = iter_pubmed_records(source, selection=selection, omitted_log=log)
        else:
            raise ValueError('Unknown corpus input format.')
        with (output / 'corpus.jsonl').open('w', encoding='utf-8', newline='\n') as target:
            for record in records:
                validate_record(record)
                target.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
                count += 1
                if count % 100000 == 0:
                    print(f'Prepared {count:,} records', flush=True)
    if count == 0:
        raise ValueError('The source contains no records.')
    report = {'status': 'COMPLETE', 'input_format': kind, 'records': count,
              'raw_sources_modified': False, 'output': 'corpus.jsonl'}
    _json(output / 'preparation.json', report)
    return report
