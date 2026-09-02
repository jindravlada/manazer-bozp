"""CONTROL-REPORT-ATTENTION-TEXT-5: priorita textů bez Qt."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.shared.constants import (
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_VYHOVUJE,
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
)
from core.shared.sluzby.control_report_attention import (
    attention_texts_for_point,
    format_attention_areas_text,
    format_neutral_attention_label,
)


def _row(**fields):
    defaults = {
        "id": 1,
        "result": CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        "source_area_label": "Požární ochrana",
        "source_section_label": "Hasicí přístroje",
        "source_control_point_id": "hp1",
        "source_control_point_label": "Hasicí přístroj je správně označen.",
        "note": "",
    }
    defaults.update(fields)
    return SimpleNamespace(**defaults)


def _finding(**fields):
    defaults = {
        "id": 1,
        "display_order": 1,
        "source_control_point_id": "hp1",
        "description": "",
        "recommended_action": "",
        "task_id": None,
    }
    defaults.update(fields)
    return SimpleNamespace(**defaults)


class ControlReportAttentionHelperTestCase(unittest.TestCase):
    def test_finding_description_beats_positive_question(self) -> None:
        row = _row()
        finding = _finding(
            description="Hasicí přístroj v místnosti váhy není dostatečně viditelný.",
        )
        text = format_attention_areas_text([row], [finding])
        self.assertEqual(
            "🟡 Hasicí přístroj v místnosti váhy není dostatečně viditelný.",
            text,
        )
        self.assertNotIn("Hasicí přístroj je správně označen.", text)

    def test_multiple_findings_same_point_keep_order_and_icon(self) -> None:
        row = _row(result=CONTROL_RESULT_NEVYHOVUJE)
        findings = [
            _finding(id=20, display_order=2, description="Druhý problém."),
            _finding(id=10, display_order=1, description="První problém."),
        ]
        text = format_attention_areas_text([row], findings)
        self.assertEqual("🔴 První problém.\n🔴 Druhý problém.", text)

    def test_duplicate_descriptions_are_not_repeated(self) -> None:
        row = _row()
        findings = [
            _finding(id=1, display_order=1, description="Stejný text."),
            _finding(id=2, display_order=2, description="Stejný text."),
        ]
        text = format_attention_areas_text([row], findings)
        self.assertEqual("🟡 Stejný text.", text)

    def test_empty_description_uses_recommended_action(self) -> None:
        row = _row()
        finding = _finding(description="", recommended_action="Doplnit označení HP.")
        self.assertEqual(
            ["Doplnit označení HP."],
            attention_texts_for_point(row, [finding]),
        )

    def test_note_before_recommended_action(self) -> None:
        row = _row(note="Přístroj je za skříní.")
        finding = _finding(recommended_action="Přemístit přístroj.")
        self.assertEqual(
            ["Přístroj je za skříní."],
            attention_texts_for_point(row, [finding]),
        )

    def test_task_title_fallback(self) -> None:
        row = _row()
        finding = _finding(id=7, description="", recommended_action="")
        texts = attention_texts_for_point(
            row,
            [finding],
            task_title_by_finding_id={7: "Zajistit viditelnost HP"},
        )
        self.assertEqual(["Zajistit viditelnost HP"], texts)

    def test_neutral_fallback_without_question(self) -> None:
        row = _row()
        text = format_attention_areas_text([row], [])
        self.assertEqual(
            "🟡 Požární ochrana — Hasicí přístroje (Vyhovuje s doporučením)",
            text,
        )
        self.assertNotIn("Hasicí přístroj je správně označen.", text)

    def test_neutral_fallback_area_only(self) -> None:
        self.assertEqual(
            "Požární ochrana (Nevyhovuje)",
            format_neutral_attention_label(
                area_label="Požární ochrana",
                section_label="",
                result=CONTROL_RESULT_NEVYHOVUJE,
            ),
        )

    def test_sort_puts_nevyhovuje_first(self) -> None:
        rec = _row(
            id=1,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            source_control_point_id="a",
            note="Doporučení A",
        )
        bad = _row(
            id=2,
            result=CONTROL_RESULT_NEVYHOVUJE,
            source_control_point_id="b",
            source_control_point_label="Jiná otázka.",
            note="Závada B",
        )
        ok = _row(
            id=3,
            result=CONTROL_RESULT_VYHOVUJE,
            source_control_point_id="c",
            note="Nemá být ve výčtu",
        )
        text = format_attention_areas_text([rec, bad, ok], [])
        self.assertEqual("🔴 Závada B\n🟡 Doporučení A", text)

    def test_unlinked_finding_is_ignored(self) -> None:
        row = _row(source_control_point_id="hp1")
        finding = _finding(
            source_control_point_id="",
            description="Nesmí se navázat podle textu otázky.",
        )
        text = format_attention_areas_text([row], [finding])
        self.assertIn("Požární ochrana — Hasicí přístroje", text)
        self.assertNotIn("Nesmí se navázat", text)


if __name__ == "__main__":
    unittest.main()
