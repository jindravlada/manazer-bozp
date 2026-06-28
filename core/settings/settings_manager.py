from pathlib import Path
import json

class SettingsManager:
    def __init__(self):
        self.dir=Path("data/nastaveni")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file=self.dir/"settings.json"
        self.data={}

    def load(self):
        if self.file.exists():
            self.data=json.loads(self.file.read_text(encoding="utf-8"))
        else:
            self.data={
                "theme":"default",
                "language":"cs",
                "window_maximized":True
            }
            self.save()

    def save(self):
        self.file.write_text(json.dumps(self.data,indent=4,ensure_ascii=False),encoding="utf-8")

    def get(self,key,default=None):
        return self.data.get(key,default)

    def set(self,key,value):
        self.data[key]=value
        self.save()

settings=SettingsManager()
