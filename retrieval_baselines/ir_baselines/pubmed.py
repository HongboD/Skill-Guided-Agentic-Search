"""Stream the original 2018 PubMed XML; retain public title and abstract text."""
import calendar
from datetime import date
import gzip
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from .pubmed_versions import version_number, source_snapshot

MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name}


def publication_date(element):
    """Use the earliest supplied publication date; partial dates use first day.

    The rule is corpus-wide and independent of topics and relevance labels.
    Precision is retained so controller reports can describe partial dates.
    """
    if element is None:
        return None
    year = element.findtext('Year')
    if year:
        month, day = element.findtext('Month'), element.findtext('Day')
        precision = 'day' if day else 'month' if month else 'year'
        month = int(month) if month and month.isdigit() else MONTHS.get((month or '').lower()[:3], 1)
        try:
            return date(int(year), month, int(day or 1)).strftime('%Y%m%d'), precision
        except ValueError:
            return None
    text = element.findtext('MedlineDate', '')
    years = re.findall(r'\b(?:18|19|20)\d{2}\b', text)
    if not years:
        return None
    month = next((MONTHS[token.lower()[:3]] for token in text.split() if token.lower()[:3] in MONTHS), 1)
    return date(int(min(years)), month, 1).strftime('%Y%m%d'), 'medline_date'


def text(element):
    return '' if element is None else ' '.join(''.join(element.itertext()).split())


def record_from_article(article, source):
    book = article.tag == 'PubmedBookArticle'
    citation = article.find('BookDocument' if book else 'MedlineCitation')
    if citation is None:
        raise ValueError('missing_pubmed_citation')
    ident = citation.findtext('PMID', '').strip()
    if not ident.isdigit():
        raise ValueError('missing_pubmed_id')
    data = citation if book else citation.find('Article')
    if data is None:
        raise ValueError('missing_pubmed_article')
    title = text(data.find('ArticleTitle'))
    abstracts = []
    for part in data.findall('./Abstract/AbstractText'):
        label = part.get('Label')
        body = text(part)
        abstracts.append((label + ': ' if label else '') + body)
    abstract = '\n'.join(abstracts)
    candidates = [publication_date(x) for x in data.findall('./ArticleDate')]
    candidates.append(publication_date(data.find('./Book/PubDate' if book else './Journal/JournalIssue/PubDate')))
    dates = [value for value in candidates if value]
    metadata = {'doc_id': ident, 'pmid': ident, 'source_id': source,
                'abstract_missing': not bool(abstract), 'publication_date_missing': not bool(dates)}
    if dates:
        value, precision = min(dates)
        metadata.update(publication_date=value, publication_date_precision=precision)
    return {'id': ident, 'title': title, 'contents': '\n'.join(x for x in (title, abstract) if x), 'metadata': metadata}


def pubmed_files(directory):
    directory = Path(directory)
    expected = [directory / f'pubmed18n{i:04d}.xml.gz' for i in range(1, 929)]
    missing = [path.name for path in expected if not path.is_file()]
    if missing:
        raise ValueError('incomplete_pubmed2018_baseline:' + ','.join(missing[:3]))
    return expected


def iter_pubmed_records(directory, *, wanted_ids=None, selection=None, omitted_log=None, selection_stats=None):
    expected = pubmed_files(directory)
    if selection is not None:
        if selection.get('status') != 'COMPLETE' or selection['source_files'] != source_snapshot(expected):
            raise ValueError('pubmed_version_selection_does_not_match_sources')
        if omitted_log is None:
            raise ValueError('pubmed_version_selection_requires_omission_log')
    source_count = omitted = emitted = 0
    for path in expected:
        record_number = 0
        with gzip.open(path, 'rb') as stream:
            events = ET.iterparse(stream, events=('start', 'end'))
            _, root = next(events)
            for event, element in events:
                if event == 'end' and element.tag in ('PubmedArticle', 'PubmedBookArticle'):
                    record_number += 1
                    source_count += 1
                    prefix = 'BookDocument' if element.tag == 'PubmedBookArticle' else 'MedlineCitation'
                    ident = element.findtext(prefix + '/PMID', '').strip()
                    if wanted_ids is None or ident in wanted_ids:
                        pmid = element.find(prefix + '/PMID')
                        version = version_number(pmid.get('Version') if pmid is not None else None)
                        winner = selection['selected_versions'].get(ident) if selection is not None else None
                        if winner and version < winner['version']:
                            omitted += 1
                            omitted_log.write(json.dumps({'id': ident, 'omitted_version': version,
                                'omitted_source_id': path.name, 'omitted_record_number': record_number,
                                'retained': winner, 'reason': 'older_citation_version'}, ensure_ascii=False) + '\n')
                            omitted_log.flush()
                        else:
                            emitted += 1
                            yield record_from_article(element, path.name)
                    root.clear()
    if selection is not None:
        if source_count != selection['source_records'] or selection['source_files'] != source_snapshot(expected):
            raise ValueError('pubmed_sources_changed_during_index_build')
        if wanted_ids is None and source_count != emitted + omitted:
            raise ValueError('pubmed_version_record_counts_disagree')
        if selection_stats is not None:
            selection_stats.update(source_records=source_count, omitted_older_versions=omitted,
                                   selected_records=emitted)
