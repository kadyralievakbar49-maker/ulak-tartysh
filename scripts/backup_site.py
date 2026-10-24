"""Create a consistent SQLite and uploaded-assets backup without copying secrets."""
from contextlib import closing
import argparse
from datetime import datetime
from pathlib import Path
import os
import sqlite3
import tarfile
import tempfile
import time
from zoneinfo import ZoneInfo


def create_backup(root, database, output):
    root, database, output = Path(root).resolve(), Path(database).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(ZoneInfo('Asia/Bishkek')).strftime('%Y%m%d-%H%M%S-%f')
    target = output / f'ulak-tartysh-{stamp}.tar.gz'
    with tempfile.TemporaryDirectory() as temporary:
        snapshot = Path(temporary) / 'database.db'
        with closing(sqlite3.connect(f'file:{database}?mode=ro', uri=True)) as source, closing(sqlite3.connect(snapshot)) as destination:
            source.backup(destination)
            if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Database integrity check failed')
        with tarfile.open(target, 'w:gz') as archive:
            archive.add(snapshot, arcname='database.db')
            for folder in ['static/uploads', 'static/documents']:
                if (root / folder).exists():
                    archive.add(root / folder, arcname=folder)
    os.chmod(target, 0o600)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default=os.getenv('DATABASE_PATH', 'database.db'))
    parser.add_argument('--output', default='backups')
    parser.add_argument('--interval-hours', type=float, help='Repeat backups at this interval')
    parser.add_argument('--keep', type=int, help='Retain this many archives created by this script')
    args = parser.parse_args()
    if args.interval_hours is not None and args.interval_hours <= 0:
        parser.error('--interval-hours must be positive')
    if args.keep is not None and args.keep < 1:
        parser.error('--keep must be positive')
    while True:
        archive = create_backup(Path(__file__).resolve().parents[1], args.database, args.output)
        print(archive, flush=True)
        if args.keep:
            archives = sorted(archive.parent.glob('ulak-tartysh-*.tar.gz'), reverse=True)
            for older in archives[args.keep:]:
                older.unlink()
        if args.interval_hours is None:
            break
        time.sleep(args.interval_hours * 3600)
