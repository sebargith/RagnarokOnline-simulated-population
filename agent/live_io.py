"""Bounded local runtime files. No bridge access from observer/control commands."""
from contextlib import contextmanager
import json
import msvcrt
from pathlib import Path


@contextmanager
def exclusive(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


class RingLog:
    def __init__(self, path, limit=1024*1024, backups=3):
        self.path, self.limit, self.backups = Path(path), limit, backups
        self.file = self.path.open('a', encoding='utf-8', newline='\n')
        self.size = self.path.stat().st_size

    def write(self, text):
        size = len(text.encode('utf-8'))
        if size > self.limit:
            raise ValueError('Log record exceeds segment budget')
        if self.size+size > self.limit:
            self.file.close()
            self.path.with_name(self.path.name+'.'+str(self.backups)).unlink(missing_ok=True)
            for index in range(self.backups-1, 0, -1):
                source = self.path.with_name(self.path.name+'.'+str(index))
                if source.exists():
                    source.replace(self.path.with_name(self.path.name+'.'+str(index+1)))
            self.path.replace(self.path.with_name(self.path.name+'.1'))
            self.file = self.path.open('w', encoding='utf-8', newline='\n')
            self.size = 0
        self.file.write(text)
        self.file.flush()
        self.size += size

    def close(self):
        self.file.close()
