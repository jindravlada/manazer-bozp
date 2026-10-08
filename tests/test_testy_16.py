"""TESTY-16: grafické úpravy tištěného papírového testu."""

from __future__ import annotations

import html
import importlib
import os
import re
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-16-"))
_EXAM_DAY = date(2026, 10, 8)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ANSWER_KIND_TEXT,
        EXAMINER_MODE_SINGLE,
        PAPER_TEST_INSTRUCTION,
        VALIDITY_UNIT_YEARS,
    )
    from moduly.testy.sluzby.exam_protocol_layout import (
        BLANK_EXAM_DATE_LINE,
        PAPER_RESULT_OPTIONS,
        paper_result_text,
    )
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
    from moduly.testy.sluzby.paper_test_export_service import (
        _header_paragraphs,
        paper_test_export_service,
        variant_label,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import test_exam_service
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )


def _paragraph_text(paragraph) -> str:
    return "".join(run.text for run in paragraph.runs)


def _plain(xml: str) -> str:
    text = xml.replace("<text:line-break/>", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _style_body(xml: str, name: str) -> str:
    start = xml.find(f'style:name="{name}"')
    if start < 0:
        raise AssertionError(name)
    end = xml.find("</style:style>", start)
    return xml[start:end]


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


class PaperTestAppearanceTestCase(unittest.TestCase):
    def test_header_joins_name_and_hides_variant(self) -> None:
        exam = SimpleNamespace(
            id=16,
            test_name="BOZP",
            employee_display_name="Jiří Šebek",
            employee_title_before="",
            employee_first_name="Jiří",
            employee_last_name="Šebek",
            employee_title_after="",
            employee_personal_number="60070071",
            employee_workplace_name="Hala",
            written_duration_seconds=120,
        )
        paragraphs = _header_paragraphs(exam, for_key=False)
        texts = [_paragraph_text(item) for item in paragraphs]
        self.assertEqual(paragraphs[0].style, "WrittenTitle")
        self.assertEqual(texts[0], "Test: BOZP")
        self.assertEqual(texts[1], "Jiří Šebek; Osobní číslo: 60070071")
        self.assertEqual(paragraphs[1].style, "WrittenMeta")
        self.assertIn("Pracoviště: Hala", texts)
        self.assertIn(BLANK_EXAM_DATE_LINE, texts)
        self.assertIn(PAPER_TEST_INSTRUCTION, texts)
        self.assertNotIn("Čas na písemnou část", "\n".join(texts))
        self.assertEqual(exam.written_duration_seconds, 120)
        self.assertNotIn(variant_label(exam), texts)

    def test_printed_test_matches_the_layout(self) -> None:
        workplace = settings_service.save_workplace(name="Hala")
        role = responsibility_role_service.create_role(name="Svářeč 16")
        employee = test_employee_service.create_employee(
            personal_number="60070071",
            first_name="Jiří",
            last_name="Šebek",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
        )
        examiner = test_employee_service.create_employee(
            personal_number="60070072",
            first_name="Adam",
            last_name="Zkušební",
            title_before="Bc.",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
            may_examine=True,
        )
        topic = written_question_topic_service.create_topic(name="BOZP okruh")
        written_question_service.create_question(
            topic_id=topic.id,
            text="Kde je únikový východ?",
            answer_kind=ANSWER_KIND_TEXT,
            answers=[
                WrittenAnswerInput(text="u schodiště", is_correct=True),
                WrittenAnswerInput(text="ve skladu"),
                WrittenAnswerInput(text="v kanceláři"),
            ],
        )
        oral = oral_question_topic_service.create_topic(name="Ústní 16")
        oral_question_service.create_question(topic_id=oral.id, text="Popište hlášení úrazu")
        definition = test_definition_service.create_test(
            name="BOZP",
            uses_written=True,
            uses_oral=True,
            allowed_wrong_answers=0,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_SINGLE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
            oral_topics=[TestTopicQuota(oral.id, 1)],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=definition.id,
            exam_date=_EXAM_DAY,
            examiner_id=examiner.id,
            rng=PrefixReverse(),
        )
        before = (
            exam.status,
            exam.written_result,
            exam.exam_result,
            tuple(
                (row.position, row.text)
                for row in test_exam_service.get_written_questions(exam.id)
            ),
        )
        target = _TMP / "test-16.odt"
        paper_test_export_service.export(exam.id, target)
        fresh = test_exam_service.get_exam(exam.id)
        assert fresh is not None
        self.assertEqual(
            (
                fresh.status,
                fresh.written_result,
                fresh.exam_result,
                tuple(
                    (row.position, row.text)
                    for row in test_exam_service.get_written_questions(exam.id)
                ),
            ),
            before,
        )

        with zipfile.ZipFile(target) as archive:
            content = archive.read("content.xml").decode("utf-8")
            styles = archive.read("styles.xml").decode("utf-8")
        ElementTree.fromstring(content)
        ElementTree.fromstring(styles)
        plain = _plain(content)
        title = _style_body(content, "WrittenTitle")
        meta = _style_body(content, "WrittenMeta")
        result = _style_body(content, "ProtocolResult")
        self.assertIn('fo:font-size="16pt"', title)
        self.assertIn('fo:font-weight="bold"', title)
        self.assertIn('fo:text-align="center"', title)
        self.assertIn('fo:font-size="12pt"', meta)
        self.assertIn('fo:wrap-option="no-wrap"', result)
        self.assertIn('fo:font-size="12pt"', result)

        self.assertIn("Test: BOZP", plain)
        self.assertIn("Jiří Šebek; Osobní číslo: 60070071", plain)
        self.assertIn("Pracoviště: Hala", plain)
        self.assertIn(BLANK_EXAM_DATE_LINE, plain)
        self.assertIn(PAPER_TEST_INSTRUCTION, plain)
        self.assertNotIn("Čas na písemnou část", plain)
        self.assertEqual(fresh.written_duration_seconds, 60)
        self.assertEqual(
            test_definition_service.get_test(definition.id).seconds_per_question,
            60,
        )
        self.assertNotIn(variant_label(fresh), plain)
        self.assertIn(variant_label(fresh), styles)
        self.assertIn(f'<style:footer><text:p text:style-name="WrittenVariant">{variant_label(fresh)}</text:p>', styles)

        for label in (
            "Výsledek písemné části:",
            "Výsledek ústní části:",
            "CELKOVÝ VÝSLEDEK ZKOUŠKY:",
        ):
            line = paper_result_text(label)
            self.assertIn(line, plain)
            self.assertNotIn("\n", line)
            escaped = html.escape(line, quote=False)
            self.assertIn(
                f'<text:p text:style-name="ProtocolResult">{escaped}</text:p>'
                '<text:p text:style-name="ProtocolResultGap">&#160;</text:p>',
                content,
            )
        self.assertEqual(plain.count(PAPER_RESULT_OPTIONS), 3)
        self.assertEqual(content.count('text:style-name="ProtocolResultGap"'), 3)
        self.assertIn("1. Kde je únikový východ?", plain)
        self.assertIn("u schodiště", plain)
        self.assertIn("ve skladu", plain)
        self.assertIn("v kanceláři", plain)
        self.assertIn("Popište hlášení úrazu", plain)
        self.assertIn(
            "S výsledkem písemné části souhlasím, špatné odpovědi mi byly vysvětleny:",
            plain,
        )
        self.assertEqual(plain.count("Zkoušený(á):"), 2)
        self.assertIn("Zkoušející", plain)
        self.assertLess(plain.index("CELKOVÝ VÝSLEDEK ZKOUŠKY:"), plain.rindex("Zkoušený(á):"))


if __name__ == "__main__":
    unittest.main()
