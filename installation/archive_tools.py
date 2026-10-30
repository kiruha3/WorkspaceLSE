"""Archive operations using Python's bundled gzip/lzma, independent of tar/xz on PATH."""
import argparse
import os
import tarfile
import zipfile


def filesystem_path(path):
    value = os.path.abspath(os.fspath(path))
    if os.name == 'nt' and not value.startswith('\\\\?\\'):
        value = '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value
    return value


def extraction_filter(member, destination):
    filtered = tarfile.data_filter(member, destination)
    if filtered is not None and os.name == 'nt':
        # Extended Windows paths require backslashes, including directory metadata.
        filtered = filtered.replace(
            name=os.path.normpath(filtered.name),
            linkname=os.path.normpath(filtered.linkname) if filtered.linkname else '',
        )
    return filtered


def extract_postgres(source, destination):
    target = filesystem_path(destination)
    os.makedirs(target, exist_ok=True)
    with zipfile.ZipFile(filesystem_path(source)) as package:
        with package.open('postgres-windows-x86_64.txz') as contents:
            with tarfile.open(fileobj=contents, mode='r|xz') as archive:
                archive.extractall(target, filter=extraction_filter)


def extract_cache(source, destination):
    target = filesystem_path(destination)
    os.makedirs(target, exist_ok=True)
    with tarfile.open(filesystem_path(source), 'r:gz') as archive:
        archive.extractall(target, filter=extraction_filter)


def pack_cache(source, destination):
    target = filesystem_path(destination)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with tarfile.open(target, 'w:gz') as archive:
        archive.add(filesystem_path(os.path.join(source, '_cacache')), arcname='_cacache')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('postgres', 'extract', 'pack-cache'))
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    {'postgres': extract_postgres, 'extract': extract_cache, 'pack-cache': pack_cache}[args.command](args.source, args.destination)
    print('Archive operation completed: ' + args.command)
