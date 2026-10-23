import json
import shutil
import zipfile
import os
import time
import uuid
from pathlib import Path
from datetime import datetime

class BackupService:
    def __init__(self, history_dir: str, backup_dir: str = None):
        self._history_dir = Path(history_dir)
        self._backup_dir = Path(backup_dir) if backup_dir else Path(history_dir).parent / 'backups'
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> dict:
        unique_id = uuid.uuid4().hex[:6]
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S') + '_' + unique_id
        zip_name = f'backup_{timestamp}.zip'
        zip_path = self._backup_dir / zip_name
        file_count = 0
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in Path(self._history_dir).glob('*.json'):
                zf.write(f, f.name)
                file_count += 1
                
        return {
            'backup_file': str(zip_path),
            'file_count': file_count,
            'timestamp': timestamp,
            'size_bytes': zip_path.stat().st_size if zip_path.exists() else 0
        }

    def list_backups(self) -> list:
        backups = []
        for f in sorted(self._backup_dir.glob('backup_*.zip'), reverse=True):
            backups.append({
                'name': f.name,
                'size_bytes': f.stat().st_size,
                'created': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
        return backups

    def delete_old_backups(self, keep_count: int = 5) -> int:
        backups = sorted(self._backup_dir.glob('backup_*.zip'))
        to_delete = backups[:-keep_count] if len(backups) > keep_count else []
        for f in to_delete:
            f.unlink()
        return len(to_delete)
