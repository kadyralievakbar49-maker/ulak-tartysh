"""Read-only audit of local content and file references; never invents or deletes data."""
import argparse
import json
from pathlib import Path
import sqlite3
from urllib.parse import unquote, urlparse
from contextlib import closing

ROOT = Path(__file__).resolve().parents[1]


def audit(database):
    report = {'database_integrity': '', 'missing_local_files': [], 'external_links_not_checked': 0, 'horse_records_to_review': []}
    with closing(sqlite3.connect(f'file:{Path(database).resolve()}?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        report['database_integrity'] = conn.execute('PRAGMA integrity_check').fetchone()[0]
        for table, fields in {'horses':['photo_url'], 'players':['photo_url'], 'teams':['photo_url'], 'news':['img_url'], 'videos':['video_url','thumbnail'], 'photo_albums':['cover_url'], 'photos':['photo_url'], 'documents':['file_url'], 'regulations':['file_path']}.items():
            for row in conn.execute(f'SELECT id,{",".join(fields)} FROM {table}'):
                for field in fields:
                    value=row[field] or ''
                    parsed=urlparse(value)
                    if parsed.scheme or parsed.netloc:
                        report['external_links_not_checked']+=1
                        continue
                    path=unquote(parsed.path)
                    if path.startswith('/documents/'):
                        relative='static/documents/'+path[len('/documents/'):]
                    elif path.startswith(('/static/','static/')):
                        relative=path.lstrip('/')
                    else:
                        continue
                    candidate=(ROOT/relative).resolve()
                    if not candidate.is_relative_to(ROOT/'static') or not candidate.is_file():
                        report['missing_local_files'].append({'table':table,'id':row['id'],'field':field,'path':path})
        for row in conn.execute('SELECT * FROM horses WHERE is_active=1'):
            reasons=[]
            if row['is_for_sale'] and not row['phone']: reasons.append('sale_without_contact')
            if row['is_for_sale'] and row['price'] is not None and row['price']<=1: reasons.append('price_1_or_less')
            if not row['description']: reasons.append('missing_description')
            if row['photo_url'] and 'placehold.co' in row['photo_url']: reasons.append('placeholder_photo')
            if reasons: report['horse_records_to_review'].append({'id':row['id'],'name':row['name'],'reasons':reasons})
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--database',default=str(ROOT/'database.db'))
    parser.add_argument('--output')
    args=parser.parse_args()
    result=json.dumps(audit(args.database),ensure_ascii=False,indent=2)
    if args.output: Path(args.output).write_text(result+'\n')
    else: print(result)
