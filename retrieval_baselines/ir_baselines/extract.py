"""Extract local ZIP input into a new directory with safe relative paths."""
from pathlib import Path
import shutil
import stat
import zipfile


def extract_zip(source, destination):
    """Preserve member bytes; reject absolute paths, links, and path traversal."""
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('Choose a new extraction directory.')
    with zipfile.ZipFile(source) as archive:
        entries, names = [], set()
        for item in archive.infolist():
            member = item.filename.replace('\\', '/')
            parts = member.split('/')
            if member.startswith('/') or any(p == '..' or ':' in p for p in parts):
                raise ValueError('Unsafe archive member: ' + member)
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Archive links are not accepted.')
            target = (destination / member).resolve()
            if not target.is_relative_to(destination) or target in names:
                raise ValueError('Duplicate or unsafe archive member: ' + member)
            names.add(target)
            entries.append((item, target))
        destination.mkdir(parents=True)
        for item, target in entries:
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source_file, target.open('xb') as output:
                shutil.copyfileobj(source_file, output)
    return {'status': 'COMPLETE', 'members': len(entries)}
