from pathlib import Path
import sqlite3

class DatabaseManager:
    def __init__(self):
        self.db_dir=Path("data/databaze")
        self.db_dir.mkdir(parents=True,exist_ok=True)
        self.db_path=self.db_dir/"manager_bozp.db"

    def initialize(self):
        conn=sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        conn.close()

database=DatabaseManager()
