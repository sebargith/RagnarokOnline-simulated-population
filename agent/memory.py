"""Identity-scoped durable records; dialogue never establishes game truth."""
import json
import sqlite3
import time


KINDS = {"observation", "reported_claim", "dialogue", "action", "commitment"}


class Memory:
    def __init__(self, path, identity):
        self.identity = identity
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS identity (id TEXT PRIMARY KEY, persona TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS records (seq INTEGER PRIMARY KEY, owner TEXT, key TEXT, kind TEXT, body TEXT, created REAL, UNIQUE(owner,key))")
        self.db.commit()

    def establish(self, persona):
        row = self.db.execute("SELECT persona FROM identity WHERE id=?", (self.identity,)).fetchone()
        if row and row[0] != persona:
            raise ValueError("Persistent identity cannot silently change")
        self.db.execute("INSERT OR IGNORE INTO identity VALUES (?,?)", (self.identity, persona))
        self.db.commit()

    def record(self, key, kind, body):
        if kind not in KINDS or len(key) > 160:
            raise ValueError("Invalid record")
        encoded = json.dumps(body, ensure_ascii=True)
        if len(encoded) > 4096:
            raise ValueError("Record too large")
        self.db.execute("INSERT OR IGNORE INTO records(owner,key,kind,body,created) VALUES (?,?,?,?,?)", (self.identity, key, kind, encoded, time.time()))
        # Commitments are a separate capped set, protected from routine-event churn.
        for category, cap in [("commitment", 16), ("other", 512)]:
            comparison = "=" if category == "commitment" else "!="
            self.db.execute(f"DELETE FROM records WHERE owner=? AND kind {comparison} 'commitment' AND seq NOT IN (SELECT seq FROM records WHERE owner=? AND kind {comparison} 'commitment' ORDER BY seq DESC LIMIT ?)", (self.identity, self.identity, cap))
        self.db.commit()

    def retrieve(self, limit=8, kinds=None):
        if not 1 <= limit <= 16:
            raise ValueError("Retrieval limit")
        kinds = list(KINDS if kinds is None else kinds)
        if not kinds or any(kind not in KINDS for kind in kinds):
            raise ValueError('Invalid retrieval categories')
        placeholders = ','.join('?' for _ in kinds)
        rows = self.db.execute(f"SELECT kind,body FROM records WHERE owner=? AND kind IN ({placeholders}) ORDER BY (kind='commitment') DESC, seq DESC LIMIT ?", (self.identity, *kinds, limit)).fetchall()
        result, size = [], 0
        for kind, body in rows:
            if size + len(body) > 2400:
                continue
            result.append({"kind": kind, "data": json.loads(body)})
            size += len(body)
        return result

    def close(self):
        self.db.close()
