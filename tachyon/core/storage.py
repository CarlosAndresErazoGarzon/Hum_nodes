"""Almacenamiento en SQLite (libreria estandar, sin dependencias externas)."""
import os
import sqlite3
import threading
import time


class Storage:
    def __init__(self, db_path="data/suelo.db"):
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS lecturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node TEXT NOT NULL,
                profundidad TEXT,
                raw INTEGER,
                humedad_pct INTEGER,
                ts REAL NOT NULL
            )"""
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_node_ts ON lecturas(node, ts)")
        self.conn.commit()

    def insert(self, data):
        with self.lock:
            self.conn.execute(
                "INSERT INTO lecturas (node, profundidad, raw, humedad_pct, ts) VALUES (?,?,?,?,?)",
                (
                    data.get("node"),
                    data.get("profundidad"),
                    data.get("raw"),
                    data.get("humedad_pct"),
                    time.time(),
                ),
            )
            self.conn.commit()

    def last_by_node(self):
        """Ultima lectura de cada nodo (para GET /lectura)."""
        with self.lock:
            cur = self.conn.execute(
                """SELECT l.node, l.profundidad, l.raw, l.humedad_pct, l.ts
                   FROM lecturas l
                   INNER JOIN (
                       SELECT node, MAX(ts) AS max_ts FROM lecturas GROUP BY node
                   ) m ON l.node = m.node AND l.ts = m.max_ts
                   ORDER BY l.node"""
            )
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def history(self, desde=None, hasta=None, node=None, limit=500):
        """Historico filtrable (para GET /history?desde=&hasta=&node=)."""
        q = "SELECT node, profundidad, raw, humedad_pct, ts FROM lecturas WHERE 1=1"
        params = []
        if desde:
            q += " AND ts >= ?"
            params.append(float(desde))
        if hasta:
            q += " AND ts <= ?"
            params.append(float(hasta))
        if node:
            q += " AND node = ?"
            params.append(node)
        q += " ORDER BY ts DESC LIMIT ?"
        params.append(int(limit))
        with self.lock:
            cur = self.conn.execute(q, params)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def contar(self):
        with self.lock:
            cur = self.conn.execute("SELECT COUNT(*) FROM lecturas")
            return cur.fetchone()[0]

    def nodos_distintos(self):
        with self.lock:
            cur = self.conn.execute("SELECT DISTINCT node FROM lecturas ORDER BY node")
            return [r[0] for r in cur.fetchall()]
