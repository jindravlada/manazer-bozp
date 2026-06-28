from pathlib import Path
from datetime import datetime


class AuditManager:
    """
    Základ auditního logu.
    Zatím zapisuje do textového souboru.
    Později bude ukládat do databáze.
    """

    def __init__(self):
        self.dir = Path("data/audit")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / "audit.log"

    def log(self, category: str, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.file.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{category}] {message}\n")


audit = AuditManager()
