import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import prepare_p5 as prep


class PrepareP5Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime = Path(self.tmp.name)
        source = self.runtime/'openkore/agent'
        source.mkdir(parents=True)
        for name in ('config.txt', 'servers.txt', 'sys.txt', 'timeouts.txt'):
            (source/name).write_text('username test\npassword test\n')
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''CREATE TABLE login(account_id INTEGER PRIMARY KEY,userid TEXT,user_pass TEXT,sex TEXT,email TEXT);
            CREATE TABLE `char`(char_id INTEGER PRIMARY KEY,account_id INTEGER,char_num INTEGER,name TEXT,class INTEGER,base_level INTEGER,job_level INTEGER,zeny INTEGER,status_point INTEGER,str INTEGER,agi INTEGER,vit INTEGER,`int` INTEGER,dex INTEGER,luk INTEGER,max_hp INTEGER,hp INTEGER,max_sp INTEGER,sp INTEGER,last_map TEXT,last_x INTEGER,last_y INTEGER,save_map TEXT,save_x INTEGER,save_y INTEGER,sex TEXT);
            CREATE TABLE inventory(char_id INTEGER,nameid INTEGER,amount INTEGER,equip INTEGER,identify INTEGER);''')
        self.created = 0
        self.db.create_function('ROW_COUNT', 0, lambda: self.created)
        def sql(text):
            for statement in text.split(';'):
                statement = statement.strip()
                if not statement or statement == 'USE ragnarok':
                    continue
                if statement == 'SET @character_created = ROW_COUNT()':
                    self.created = self.db.execute('SELECT changes()').fetchone()[0]
                    continue
                statement = statement.replace('INSERT IGNORE', 'INSERT OR IGNORE').replace('@character_created', 'ROW_COUNT()')
                if getattr(self, 'fail_inventory', False) and statement.startswith('INSERT INTO inventory'):
                    raise RuntimeError('simulated interruption')
                self.db.execute(statement)
        def query(text):
            return [list(map(str, row)) for row in self.db.execute(text.replace('ragnarok.', ''))]
        for target, value in (('bind_runtime', lambda _: None), ('query', query)):
            patcher = patch.object(prep, target, value); patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch.object(prep.m1, 'sql', sql); patcher.start(); self.addCleanup(patcher.stop)

    def test_new_and_repeated_preparation_preserves_inventory(self):
        prep.prepare(self.runtime)
        self.assertEqual(self.db.execute('SELECT nameid FROM inventory ORDER BY nameid').fetchall(), [(1201,), (2301,)])
        prep.prepare(self.runtime)
        self.assertEqual(self.db.execute('SELECT count(*) FROM inventory').fetchone()[0], 2)
        self.db.execute('DELETE FROM inventory')
        prep.prepare(self.runtime)
        self.assertEqual(self.db.execute('SELECT count(*) FROM inventory').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM login').fetchone()[0], 1)

    def test_interrupted_creation_never_infers_equipment_on_retry(self):
        self.fail_inventory = True
        with self.assertRaisesRegex(RuntimeError, 'simulated interruption'):
            prep.prepare(self.runtime)
        self.fail_inventory = False
        prep.prepare(self.runtime)
        self.assertEqual(self.db.execute('SELECT count(*) FROM inventory').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM `char`').fetchone()[0], 1)

    def test_existing_account_without_character_creates_equipment(self):
        self.db.execute("INSERT INTO login VALUES(2000031,'p5novice','existing','M','x')")
        prep.prepare(self.runtime)
        self.assertEqual(self.db.execute('SELECT count(*) FROM inventory').fetchone()[0], 2)

    def test_stock_packet_branch_and_config(self):
        ra = Path(__file__).resolve().parents[2]/'vendor/rathena'
        if not ra.exists():
            self.skipTest('Pinned rAthena source not installed')
        clif = (ra/'src/char/char_clif.cpp').read_text(encoding='utf-8')
        modern = clif.split('#elif PACKETVER >= 20120307', 1)[1].split('#else', 1)[0]
        for stat in ('str', 'agi', 'vit', 'int_', 'dex', 'luk'):
            self.assertIn(f'{stat} = 1;', modern)
        char = (ra/'src/char/char.cpp').read_text(encoding='utf-8')
        branch = char.split('#if PACKETVER < 20120307', 1)[1].split('#endif', 1)[0]
        self.assertIn('status_points = 0;', branch)
        self.assertIn('status_points = charserv_config.start_status_points;', branch.split('#else', 1)[1])
        self.assertIn('start_status_points: 48', (ra/'conf/inter_athena.conf').read_text(encoding='utf-8'))
        self.assertIn('#define PACKETVER 20130807', (ra/'src/custom/defines_pre.hpp').read_text(encoding='utf-8'))
        self.assertEqual(prep.STATUS_POINTS, 48)

if __name__ == '__main__':
    unittest.main()
