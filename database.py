from datetime import datetime, timedelta
def get_last_valid_ai_analysis():
    """Retorna o último ai_analysis válido do banco (não vazio e não mensagem de erro)."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute('SELECT ai_analysis FROM scans WHERE ai_analysis IS NOT NULL AND ai_analysis != "" ORDER BY id DESC LIMIT 1')
        row = cur.fetchone()
        if not row:
            return None
        import json
        try:
            return json.loads(row[0])
        except Exception:
            return row[0]

def get_last_scan_within_minutes(minutes=20):
    """Retorna o último registro do banco com timestamp dentro dos últimos X minutos."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        time_limit = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        cur.execute('SELECT * FROM scans WHERE timestamp > ? ORDER BY id DESC LIMIT 1', (time_limit,))
        row = cur.fetchone()
        if not row:
            return None
        keys = ['id', 'timestamp', 'device_count', 'temp_mikrotik', 'raw_json', 'ai_diagnosis']
        result = dict(zip(keys, row))
        import json
        import logging
        logger = logging.getLogger("database")
        # Converte raw_json para objeto
        raw = result['raw_json']
        try:
            raw_clean = sanitize_json_string(raw) if isinstance(raw, str) else raw
            result['raw_json'] = json.loads(raw_clean)
        except Exception as e:
            logger.info(f"Erro ao carregar raw_json: {raw}\n{e}")
            result['raw_json'] = {} if not raw else raw
        # Limpa crases de markdown e sanitiza ai_diagnosis
        ai_diag = result['ai_diagnosis']
        if isinstance(ai_diag, str):
            ai_diag_clean = sanitize_json_string(ai_diag)
            try:
                result['ai_diagnosis'] = json.loads(ai_diag_clean)
            except Exception as e:
                logger.info(f"Erro ao carregar ai_diagnosis: {ai_diag}\n{e}")
                result['ai_diagnosis'] = ai_diag_clean if ai_diag_clean else {}
        elif isinstance(ai_diag, dict):
            result['ai_diagnosis'] = ai_diag
        else:
            result['ai_diagnosis'] = {}
        return result
def sanitize_json_string(s):
    import re
    # Remove crases, quebras de linha, tabs e espaços excessivos
    s = re.sub(r"```json[\s\S]*?```|```", "", s)
    s = s.replace('\n', '').replace('\r', '').replace('\t', '').strip()
    return s
import sqlite3
from contextlib import closing
from datetime import datetime

import os
DB_PATH = os.getenv('DB_PATH', '/app/network_scanner.db')

SCANS_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    device_count INTEGER,
    temp_mikrotik REAL,
    raw_json TEXT,
    ai_analysis TEXT
);
'''

WIFI_METRICS_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS wifi_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    inet_loss_pct REAL,
    inet_jitter_ms REAL,
    inet_avg_ms REAL,
    gw_avg_ms REAL,
    dns_ms REAL
);
'''

def get_connection():
    try:
        return sqlite3.connect(DB_PATH)
    except Exception as e:
        import logging
        logger = logging.getLogger("database")
        logger.error(f"Erro ao abrir banco de dados: {e}")
        return None

def init_db():
    try:
        with closing(get_connection()) as conn:
            with conn:
                conn.execute(SCANS_TABLE_SQL)
                conn.execute(WIFI_METRICS_TABLE_SQL)
    except Exception as e:
        import logging
        logger = logging.getLogger("database")
        logger.error(f"Erro ao inicializar o banco: {e}")


def insert_wifi_metric(inet_loss_pct, inet_jitter_ms, inet_avg_ms, gw_avg_ms, dns_ms):
    try:
        with closing(get_connection()) as conn:
            with conn:
                conn.execute(
                    '''INSERT INTO wifi_metrics
                       (timestamp, inet_loss_pct, inet_jitter_ms, inet_avg_ms, gw_avg_ms, dns_ms)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (datetime.now().isoformat(),
                     inet_loss_pct, inet_jitter_ms, inet_avg_ms, gw_avg_ms, dns_ms)
                )
    except Exception as e:
        import logging
        logging.getLogger("database").error(f"Erro ao salvar wifi_metric: {e}")


def get_wifi_metrics_recent(limit: int = 60) -> list:
    """Retorna os últimos N registros de qualidade WiFi para sparklines."""
    try:
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute(
                '''SELECT timestamp, inet_loss_pct, inet_jitter_ms, inet_avg_ms, gw_avg_ms, dns_ms
                   FROM wifi_metrics ORDER BY id DESC LIMIT ?''',
                (limit,)
            )
            rows = cur.fetchall()
            keys = ['timestamp', 'inet_loss_pct', 'inet_jitter_ms', 'inet_avg_ms', 'gw_avg_ms', 'dns_ms']
            return [dict(zip(keys, r)) for r in reversed(rows)]
    except Exception:
        return []

def insert_scan(device_count, temp_mikrotik, raw_json, ai_analysis):
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                'INSERT INTO scans (timestamp, device_count, temp_mikrotik, raw_json, ai_analysis) VALUES (?, ?, ?, ?, ?)',
                (datetime.now().isoformat(), device_count, temp_mikrotik, raw_json, ai_analysis)
            )

def get_last_scan():
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM scans ORDER BY id DESC LIMIT 1')
        row = cur.fetchone()
        if not row:
            return None
        keys = ['id', 'timestamp', 'device_count', 'temp_mikrotik', 'raw_json', 'ai_diagnosis']
        result = dict(zip(keys, row))
        import json
        import logging
        logger = logging.getLogger("database")
        # Converte raw_json para objeto
        raw = result['raw_json']
        try:
            raw_clean = sanitize_json_string(raw) if isinstance(raw, str) else raw
            result['raw_json'] = json.loads(raw_clean)
        except Exception as e:
            logger.info(f"Erro ao carregar raw_json: {raw}\n{e}")
            result['raw_json'] = {} if not raw else raw
        # Limpa crases de markdown e sanitiza ai_diagnosis
        ai_diag = result['ai_diagnosis']
        if isinstance(ai_diag, str):
            ai_diag_clean = sanitize_json_string(ai_diag)
            try:
                result['ai_diagnosis'] = json.loads(ai_diag_clean)
            except Exception as e:
                logger.info(f"Erro ao carregar ai_diagnosis: {ai_diag}\n{e}")
                result['ai_diagnosis'] = ai_diag_clean if ai_diag_clean else {}
        elif isinstance(ai_diag, dict):
            result['ai_diagnosis'] = ai_diag
        else:
            result['ai_diagnosis'] = {}
        return result

# Inicializa o banco ao importar
init_db()
