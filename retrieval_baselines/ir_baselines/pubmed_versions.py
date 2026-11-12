"""Select the latest citation version in the fixed historical PubMed baseline."""
from datetime import datetime, timezone
import gzip
from pathlib import Path
from xml.parsers import expat

from .indexing import _json

POLICY = 'highest_PMID_Version_in_2018_baseline'
SOURCE = 'https://www.nlm.nih.gov/pubs/techbull/jf12/jf12_pm_versioning.html'


def version_number(value):
    value = '1' if value is None else value
    if not isinstance(value, str) or not value.isdigit() or int(value) < 1:
        raise ValueError('invalid_pubmed_version:' + str(value))
    return int(value)


def source_snapshot(paths):
    return [{'name': p.name, 'bytes': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns}
            for p in paths]


def scan_file(path):
    """Read citation PMIDs only; ignore PMIDs in references and related records."""
    parser = expat.ParserCreate()
    stack, occurrences, text = [], [], []
    count = 0
    active = None

    def start(name, attrs):
        nonlocal count, active
        stack.append(name)
        if name in ('PubmedArticle', 'PubmedBookArticle'):
            count += 1
        if name == 'PMID' and stack[-2:] in (['MedlineCitation', 'PMID'], ['BookDocument', 'PMID']):
            active = version_number(attrs.get('Version'))
            text.clear()

    def data(value):
        if active is not None:
            text.append(value)

    def end(name):
        nonlocal active
        if name == 'PMID' and active is not None:
            ident = ''.join(text).strip()
            if not ident.isdigit():
                raise ValueError('invalid_pubmed_id:' + ident)
            if active > 1:
                occurrences.append({'id': ident, 'version': active,
                                    'source_id': Path(path).name, 'record_number': count})
            active = None
        stack.pop()

    parser.StartElementHandler, parser.CharacterDataHandler, parser.EndElementHandler = start, data, end
    # Do not load external entities or DTDs. Expat parses the supplied local XML.
    with gzip.open(path, 'rb') as stream:
        parser.ParseFile(stream)
    return count, occurrences


def scan_versions(paths, report_path):
    """Make a small selection map before indexing; raw files are read only."""
    paths = list(paths)
    snapshot = source_snapshot(paths)
    started = datetime.now(timezone.utc).isoformat()
    records, occurrences, selected = 0, [], {}
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        for number, path in enumerate(paths, 1):
            count, found = scan_file(path)
            records += count
            occurrences.extend(found)
            for row in found:
                previous = selected.get(row['id'])
                if previous is None or row['version'] > previous['version']:
                    selected[row['id']] = row
            _json(report_path, {'status': 'SCANNING', 'policy': POLICY, 'started_at_utc': started,
                  'files_scanned': number, 'total_files': len(paths), 'source_records': records,
                  'versioned_pmids': len(selected), 'updated_at_utc': datetime.now(timezone.utc).isoformat()})
        if snapshot != source_snapshot(paths):
            raise ValueError('pubmed_sources_changed_during_version_scan')
        for ident, winner in selected.items():
            if sum(row['id'] == ident and row['version'] == winner['version'] for row in occurrences) != 1:
                raise ValueError('repeated_highest_pubmed_version:' + ident)
        result = {'status': 'COMPLETE', 'policy': POLICY, 'policy_source': SOURCE,
                  'started_at_utc': started, 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
                  'source_files': snapshot, 'source_records': records, 'selected_versions': selected,
                  'versioned_occurrences': occurrences}
        _json(report_path, result)
        return result
    except Exception as error:
        _json(report_path, {'status': 'FAILED', 'policy': POLICY, 'source_records': records,
                           'reason': str(error), 'time': datetime.now(timezone.utc).isoformat()})
        raise
