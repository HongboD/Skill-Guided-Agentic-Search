"""Convert prepared text into the fixed searchable record schema."""
from html.parser import HTMLParser
from pathlib import Path

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        elif tag in ('p', 'div', 'br', 'li', 'td', 'tr', 'h1', 'h2', 'h3'):
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        elif tag in ('p', 'div', 'li', 'td', 'tr', 'h1', 'h2', 'h3'):
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

def plain_html(text):
    parser = PlainText()
    parser.feed(text)
    parser.close()
    return ' '.join(''.join(parser.parts).split())

def iter_tot_records(path):
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            ident, title, body = line.rstrip('\r\n').split('\t', 2)
            yield {'id': ident, 'title': title, 'contents': title + '\n' + body, 'metadata': {'doc_id': ident}}

def iter_genomics_records(path):
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            pmid, offset, length, html = line.rstrip('\r\n').split('\t', 3)
            start, size = int(offset), int(length)
            if not pmid.isdigit() or start < 0 or size <= 0:
                raise ValueError('invalid_source_legal_span')
            yield {'id': f'{pmid}:{start}:{size}', 'title': '', 'contents': plain_html(html),
                   'metadata': {'doc_id': pmid, 'pmid': pmid, 'offset': start, 'length': size}}
