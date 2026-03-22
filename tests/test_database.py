import unittest
import os
import json
from database import get_connection, insert_scan, get_last_scan, init_db

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Usa um banco temporário para testes
        self.test_db = 'test_network_scanner.db'
        global DB_PATH
        DB_PATH = self.test_db
        init_db()

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_insert_and_get_last_scan(self):
        # Dados simulados
        device_count = 5
        temp_mikrotik = 42.5
        raw_json = json.dumps({"report": {"devices": [{"status": "Ativo"}], "mikrotik_health": {"temperature": 42.5}}})
        ai_analysis = json.dumps({"diagnosis": "OK"})
        insert_scan(device_count, temp_mikrotik, raw_json, ai_analysis)
        row = get_last_scan()
        self.assertIsNotNone(row)
        self.assertEqual(row[2], device_count)
        self.assertEqual(row[3], temp_mikrotik)
        self.assertEqual(json.loads(row[4]), json.loads(raw_json))
        self.assertEqual(json.loads(row[5]), json.loads(ai_analysis))

if __name__ == '__main__':
    unittest.main()
