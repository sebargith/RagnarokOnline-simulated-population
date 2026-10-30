import tempfile
from pathlib import Path
import unittest
from agent.memory import Memory


class MemoryTests(unittest.TestCase):
    def test_restart_isolation_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'memory.sqlite'
            first = Memory(path, 'one')
            first.establish('Patient novice')
            first.record('promise', 'commitment', {'text': 'Meet at the gate'})
            first.record('rumor', 'reported_claim', {'text': 'Aden is safe'})
            first.record('failed', 'action', {'status': 'unknown'})
            first.close()
            second = Memory(path, 'two')
            self.assertEqual(second.retrieve(), [])
            second.close()
            reopened = Memory(path, 'one')
            self.assertEqual(reopened.retrieve()[0]['kind'], 'commitment')
            self.assertIn({'kind': 'action', 'data': {'status': 'unknown'}}, reopened.retrieve())
            with self.assertRaises(ValueError):
                reopened.establish('Different person')
            reopened.close()

    def test_retention_and_duplicate_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(Path(directory) / 'memory.sqlite', 'one')
            memory.record('promise', 'commitment', {'text': 'Meet'})
            for index in range(530):
                memory.record(str(index), 'observation', {'index': index})
            memory.record('promise', 'commitment', {'text': 'Changed'})
            self.assertEqual(memory.retrieve()[0]['data']['text'], 'Meet')
            self.assertEqual(memory.db.execute('SELECT count(*) FROM records').fetchone()[0], 513)
            self.assertLessEqual(len(memory.retrieve()), 8)
            memory.close()


if __name__ == '__main__':
    unittest.main()
