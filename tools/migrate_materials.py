#!/usr/bin/env python3
"""Build a hash-verified staging tree; rclone copy never removes remote data."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DRIVE = '12nhmLr5SAhwo04TIZNJdIUSDwEtETxiL'


def destination(relative):
    parts = list(PurePosixPath(relative).parts)
    if parts and parts[0].casefold() == 'лекции':
        parts.pop(0)
    if not parts:
        return None
    subject = {'мдк': 'МДК', 'оит': 'ОИТ', 'ино': 'ИНО', 'дополнительно': 'Дополнительно'}.get(parts[0].casefold())
    if subject is None:
        return PurePosixPath('На_разбор', *parts)
    parts[0] = subject
    if subject == 'Дополнительно':
        return PurePosixPath(*parts)
    if len(parts) == 2:
        parts.insert(1, 'Учебники' if subject == 'ИНО' and 'infotech' in parts[-1].casefold() else 'Лекции')
    if len(parts) > 2 and parts[1] not in ('Лекции', 'Практики', 'Учебники'):
        return PurePosixPath('На_разбор', *parts)
    return PurePosixPath(*parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--remote', default='gdrive:')
    args = parser.parse_args()
    output = ROOT / 'migration-output'
    output.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='staging-', dir=output))
    records, seen = [], {}

    def add(name, stream, source):
        relative = destination(name)
        if relative is None or relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe source path')
        path = staging.joinpath(*relative.parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.tmp')
        sha, md5, size = hashlib.sha256(), hashlib.md5(), 0
        with temporary.open('wb') as target:
            while block := stream.read(1024 * 1024):
                sha.update(block); md5.update(block); size += len(block); target.write(block)
        digest = sha.hexdigest()
        key = str(relative)
        # Deduplicate only inside the same logical destination. PZ9 and PZ10
        # may intentionally attach the same assignment.
        duplicate = key in seen and seen[key] == digest
        if key in seen and not duplicate:
            relative = relative.with_name(relative.stem + '__' + digest[:12] + relative.suffix)
            path = staging.joinpath(*relative.parts)
            key = str(relative)
        if duplicate:
            temporary.unlink()
        else:
            temporary.replace(path)
            seen[key] = digest
        records.append(dict(source=source, destination=str(relative), sha256=digest, md5=md5.hexdigest(), size=size, duplicate=duplicate))

    local = ROOT / 'aiogram-learning' / 'лекции'
    for path in sorted(local.rglob('*')):
        if path.is_file() and not path.is_symlink() and not path.name.startswith('.'):
            with path.open('rb') as stream:
                add(str(path.relative_to(local)), stream, 'local:' + str(path.relative_to(ROOT)))
    archive = ROOT / 'aiogram-learning' / 'материалы.zip'
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                if not item.is_dir():
                    with z.open(item) as stream:
                        add(item.filename, stream, 'archive:' + item.filename)
    (output / 'manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2))
    (output / 'staging-path.txt').write_text(str(staging) + '\n')
    print(json.dumps({'sources': len(records), 'unique_destinations': len(seen), 'duplicates': sum(r['duplicate'] for r in records), 'apply': args.apply}), flush=True)
    common = ['--drive-root-folder-id', DRIVE]
    if args.apply:
        # Verify existing collisions before uploading. Never silently replace
        # an existing Drive document with different contents.
        remote = json.loads(subprocess.check_output(['rclone', 'lsjson', args.remote, '--recursive', '--files-only', '--hash', *common]))
        for f in remote:
            path = staging / f['Path']
            if path.exists():
                with path.open('rb') as stream:
                    checksum = hashlib.file_digest(stream, 'md5').hexdigest()
                if checksum != f.get('Hashes', {}).get('MD5'):
                    raise SystemExit('Remote collision; review before upload: ' + f['Path'])
    command = ['rclone', 'copy', str(staging), args.remote, '--checksum', '--immutable', *common]
    if not args.apply:
        command.append('--dry-run')
    subprocess.run(command, check=True)
    if args.apply:
        subprocess.run(['rclone', 'check', str(staging), args.remote, '--one-way', *common], check=True)
    print(json.dumps({'sources': len(records), 'unique_destinations': len(seen), 'duplicates': sum(r['duplicate'] for r in records), 'apply': args.apply}))


if __name__ == '__main__':
    main()
