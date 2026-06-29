from dataclasses import dataclass

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class SedmeroPrinciple:
    number: int
    title: str
    text: str
    explanation: str = ""


SEDMERO_INTRO = (
    "Vyšetřování mimořádné události není hledáním viníka.\n"
    "Je hledáním příčin a příležitostí ke zlepšení systému."
)

SEDMERO_PRINCIPLES: tuple[SedmeroPrinciple, ...] = (
    SedmeroPrinciple(1, "Proč vyšetřujeme?", "Nehledej viníka. Hledej příčiny."),
    SedmeroPrinciple(2, "Jak přemýšlíme?", "Každá mimořádná událost má více příčin."),
    SedmeroPrinciple(
        3,
        "Jak chápeme lidskou chybu?",
        "Lidská chyba bývá důsledkem, ne kořenovou příčinou.",
    ),
    SedmeroPrinciple(4, "Na čem stavíme závěry?", "Na důkazech, ne na domněnkách."),
    SedmeroPrinciple(5, "Co vlastně hledáme?", "Příčiny, které lze odstranit."),
    SedmeroPrinciple(6, "Jak navrhujeme řešení?", "Zlepšujeme systém, ne hledáme viníka."),
    SedmeroPrinciple(7, "Kdy máme hotovo?", "Až ověříme účinnost přijatých opatření."),
)


class MuSedmeroDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Sedmero vyšetřování")
        self.resize(560, 580)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        header = QLabel("Sedmero vyšetřování")
        header.setObjectName("SectionTitle")
        outer.addWidget(header)

        intro = QLabel(SEDMERO_INTRO)
        intro.setWordWrap(True)
        outer.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        principles_layout = QVBoxLayout(content)
        principles_layout.setContentsMargins(0, 0, 0, 0)
        principles_layout.setSpacing(16)

        for principle in SEDMERO_PRINCIPLES:
            principles_layout.addWidget(self._build_principle_widget(principle))

        principles_layout.addStretch()
        scroll.setWidget(content)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        outer.addWidget(buttons)

    def _build_principle_widget(self, principle: SedmeroPrinciple) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title_label = QLabel(f"{principle.number}. {principle.title}")
        title_label.setWordWrap(True)
        title_font = QFont(title_label.font())
        title_font.setBold(True)
        title_label.setFont(title_font)

        text_label = QLabel(principle.text)
        text_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(text_label)

        if principle.explanation.strip():
            explanation_label = QLabel(principle.explanation.strip())
            explanation_label.setWordWrap(True)
            layout.addWidget(explanation_label)

        return container
