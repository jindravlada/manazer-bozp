from pathlib import Path

class ThemeManager:
    def __init__(self):
        self.current_theme="default"

    def load(self,name:str="default")->str:
        self.current_theme=name
        return name

theme=ThemeManager()
