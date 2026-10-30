"""Durable fixed-offer transfer journal. Unknown is reconciled, never replayed."""
import json
import sqlite3
import subprocess
import time
import uuid


def server_balances(runtime):
    """Read-only verifier, never supplied to a player mind or action planner."""
    query = ('SELECT c.account_id,c.zeny,COALESCE(SUM(i.amount),0) '
             'FROM ragnarok.`char` c LEFT JOIN ragnarok.inventory i '
             'ON i.char_id=c.char_id AND i.nameid=909 '
             'WHERE c.account_id IN (2000010,2000011) GROUP BY c.account_id,c.zeny')
    output = subprocess.check_output([str(runtime.parent/'vendor/mariadb/bin/mariadb.exe'),
        '--defaults-file='+str(runtime/'mariadb/root.ini'), '--batch', '--skip-column-names', '--execute', query],
        text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    result = {}
    for line in output.splitlines():
        account, zeny, item = map(int, line.split())
        result[{2000010: 'agent', 2000011: 'peer'}[account]] = {'jellopy': item, 'zeny': zeny}
    if set(result) != {'agent', 'peer'}:
        raise RuntimeError('Both fixture accounts required for verification')
    return result


def balances(snapshot):
    return {'jellopy': sum(i['amount'] for i in snapshot['inventory'] if i['name_id'] == 909), 'zeny': snapshot['zeny']}


def reconcile(before, after):
    expected = {
        'agent': {'jellopy': before['agent']['jellopy']-1, 'zeny': before['agent']['zeny']+10},
        'peer': {'jellopy': before['peer']['jellopy']+1, 'zeny': before['peer']['zeny']-10}}
    if after == expected:
        return 'completed'
    if after == before:
        return 'not_applied'
    return 'ambiguous'


class TradeLedger:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS trades(id TEXT PRIMARY KEY, body TEXT, status TEXT)')
        self.db.commit()

    def unresolved(self):
        rows = self.db.execute("SELECT id,body FROM trades WHERE status IN ('unknown','ambiguous')").fetchall()
        return [(key, json.loads(body)) for key, body in rows]

    def begin(self, before, sessions):
        if self.unresolved():
            raise RuntimeError('Unreconciled trade blocks every new transfer')
        key = uuid.uuid4().hex
        body = {'before': before, 'sessions': sessions, 'created': time.time(), 'offer': 'one Jellopy for ten Zeny'}
        self.db.execute('INSERT INTO trades VALUES (?,?,?)', (key, json.dumps(body), 'unknown'))
        self.db.execute("DELETE FROM trades WHERE status IN ('completed','not_applied') AND rowid NOT IN (SELECT rowid FROM trades ORDER BY rowid DESC LIMIT 128)")
        self.db.commit()
        return key

    def finish(self, key, fresh_snapshots, authoritative):
        row = self.db.execute('SELECT body FROM trades WHERE id=?', (key,)).fetchone()
        if not row:
            raise ValueError('Unknown transfer')
        body = json.loads(row[0])
        for who in ('agent', 'peer'):
            snapshot = fresh_snapshots[who]
            if (not 0 <= time.time()*1000-snapshot['time_ms'] <= 2500 or snapshot['session'] == body['sessions'][who]
                or not snapshot['data'].get('inventory_ready') or not snapshot['data'].get('connected') or snapshot['data']['deal']['name']):
                raise ValueError('Fresh full-login inventory on both sides required')
        after = {who: balances(s['data']) for who, s in fresh_snapshots.items()}
        if after != authoritative:
            raise ValueError('Client inventory has not matched authoritative persisted balances')
        status = reconcile(body['before'], after)
        body.update(after=after, authoritative=authoritative, reconciliation=status, observation_ids={who: s['id'] for who, s in fresh_snapshots.items()})
        self.db.execute('UPDATE trades SET body=?,status=? WHERE id=?', (json.dumps(body), status, key))
        self.db.commit()
        return body

    def close(self):
        self.db.close()
