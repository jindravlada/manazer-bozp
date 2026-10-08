"""TESTY-SEC-3: souběžné uložení odpovědi a vyhodnocení zkoušky."""

from __future__ import annotations

import importlib
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="testy-sec3-"))
_STARTED = datetime(2026, 10, 8, 9, 0, 0)
_TRIALS = 24

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
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_STARTED,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_FINISH_EXPIRED,
        WRITTEN_FINISH_SUBMITTED,
        WRITTEN_RESULT_FAILED,
        WRITTEN_RESULT_PASSED,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import test_exam_service
    from moduly.testy.sluzby.written_exam_service import (
        WrittenExamClosed,
        written_exam_service,
    )
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )


class _Rng:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        return None


def _prepare(employee_id: int, test_id: int):
    return test_exam_service.prepare_exam(
        employee_id=employee_id,
        test_id=test_id,
        exam_date=_STARTED.date(),
        rng=_Rng(),
    )


class WrittenExamTransactionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        workplace = settings_service.save_workplace(name="PROVOZ_SEC3")
        role = responsibility_role_service.create_role(name="Mistr SEC3")
        cls.employee = test_employee_service.create_employee(
            personal_number="sec3",
            first_name="Eva",
            last_name="Souběžná",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
        )
        topic = written_question_topic_service.create_topic(name="OKRUH_SEC3")
        written_question_service.create_question(
            topic_id=topic.id,
            text="Otázka souběhu",
            answer_kind=ANSWER_KIND_TEXT,
            answers=[
                WrittenAnswerInput(text="správně", is_correct=True),
                WrittenAnswerInput(text="špatně"),
                WrittenAnswerInput(text="další"),
            ],
        )
        cls.test = test_definition_service.create_test(
            name="Souběh",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )

    def test_concurrent_save_and_submit_keep_answer_and_result_together(self) -> None:
        for correct in (True, False):
            saved = 0
            rejected = 0
            for trial in range(_TRIALS):
                exam, question, answer = self._started_answer(correct)
                save = lambda: written_exam_service.save_choice(
                    exam.id,
                    question.exam_question_id,
                    answer.id,
                    now=_STARTED + timedelta(seconds=5),
                )
                finish = lambda: written_exam_service.submit(
                    exam.id,
                    now=_STARTED + timedelta(seconds=5),
                )
                if trial % 2 == 0:
                    outcome = self._race(save, finish)
                    save_result, finish_result = outcome["a"], outcome["b"]
                else:
                    outcome = self._race(finish, save)
                    finish_result, save_result = outcome["a"], outcome["b"]
                self._assert_no_lock(outcome)
                self.assertEqual(finish_result, ("ok", WRITTEN_FINISH_SUBMITTED))
                if save_result[0] == "ok":
                    saved += 1
                    self._assert_counted(exam.id, answer.id, correct)
                else:
                    rejected += 1
                    self.assertIsInstance(save_result[1], WrittenExamClosed)
                    self._assert_unanswered(exam.id)
            self.assertGreater(saved, 0, "uložení nikdy nepředběhlo vyhodnocení")
            self.assertGreater(rejected, 0, "vyhodnocení nikdy nepředběhlo uložení")

    def test_two_submits_do_not_rewrite_the_result(self) -> None:
        for _trial in range(_TRIALS):
            exam, _question, _answer = self._started_answer(True)
            moment = _STARTED + timedelta(seconds=5)
            outcome = self._race(
                lambda: written_exam_service.submit(exam.id, now=moment),
                lambda: written_exam_service.submit(exam.id, now=moment),
            )
            self._assert_no_lock(outcome)
            successes = [item for item in outcome.values() if item[0] == "ok"]
            failures = [item for item in outcome.values() if item[0] == "err"]
            self.assertEqual(len(successes), 1)
            self.assertEqual(successes[0][1], WRITTEN_FINISH_SUBMITTED)
            self.assertEqual(len(failures), 1)
            self.assertIsInstance(failures[0][1], WrittenExamClosed)
            before = self._snapshot(exam.id)
            with self.assertRaises(WrittenExamClosed):
                written_exam_service.submit(
                    exam.id,
                    now=moment + timedelta(seconds=1),
                )
            self.assertEqual(self._snapshot(exam.id), before)
            self._assert_unanswered(exam.id)

    def test_save_racing_expiry_cannot_split_answer_from_result(self) -> None:
        saved = 0
        rejected = 0
        for trial in range(_TRIALS):
            exam, question, answer = self._started_answer(True)
            marked = _STARTED + timedelta(seconds=20)
            written_exam_service.note_running_mark(exam.id, now=marked, force=True)
            before_mark = test_exam_service.get_exam(exam.id).written_time_mark
            save = lambda: written_exam_service.save_choice(
                exam.id,
                question.exam_question_id,
                answer.id,
                now=_STARTED + timedelta(seconds=5),
            )
            expire = lambda: written_exam_service.sync_deadline(
                exam.id,
                now=_STARTED + timedelta(seconds=90),
            )
            if trial % 2 == 0:
                outcome = self._race(save, expire)
                save_result, expire_result = outcome["a"], outcome["b"]
            else:
                outcome = self._race(expire, save)
                expire_result, save_result = outcome["a"], outcome["b"]
            self._assert_no_lock(outcome)
            self.assertEqual(expire_result, ("ok", WRITTEN_FINISH_EXPIRED))
            fresh = test_exam_service.get_exam(exam.id)
            assert fresh is not None
            self.assertEqual(fresh.status, EXAM_STATUS_COMPLETED)
            self.assertEqual(fresh.written_finish_reason, WRITTEN_FINISH_EXPIRED)
            self.assertEqual(fresh.written_started_at, _STARTED)
            self.assertGreaterEqual(fresh.written_time_mark, before_mark)
            if save_result[0] == "ok":
                saved += 1
                self._assert_counted(exam.id, answer.id, True)
            else:
                rejected += 1
                self.assertIsInstance(save_result[1], WrittenExamClosed)
                self._assert_unanswered(exam.id)
        self.assertGreater(saved, 0, "uložení nikdy nepředběhlo vypršení")
        self.assertGreater(rejected, 0, "vypršení nikdy nepředběhlo uložení")

    def test_overlapping_saves_keep_a_single_consistent_choice(self) -> None:
        winners: set[int] = set()
        for _trial in range(_TRIALS):
            exam, question, correct = self._started_answer(True)
            wrong = self._other_answer(question.exam_question_id, correct.id)
            moment = _STARTED + timedelta(seconds=5)
            outcome = self._race(
                lambda: written_exam_service.save_choice(
                    exam.id,
                    question.exam_question_id,
                    correct.id,
                    now=moment,
                ),
                lambda: written_exam_service.save_choice(
                    exam.id,
                    question.exam_question_id,
                    wrong.id,
                    now=moment + timedelta(seconds=1),
                ),
            )
            self._assert_no_lock(outcome)
            self.assertEqual(outcome["a"][0], "ok")
            self.assertEqual(outcome["b"][0], "ok")
            stored = written_exam_service.choices(exam.id)
            self.assertEqual(len(stored), 1)
            answers = {
                item.id: item
                for item in test_exam_service.get_written_answers(question.exam_question_id)
            }
            chosen = answers[stored[0].exam_answer_id]
            self.assertEqual(stored[0].selected_letter, chosen.letter)
            winners.add(int(chosen.id))
            fresh = test_exam_service.get_exam(exam.id)
            assert fresh is not None
            self.assertEqual(fresh.status, EXAM_STATUS_STARTED)
            self.assertEqual(fresh.written_finish_reason, "")
            self.assertIsNone(fresh.written_result)
            self.assertGreaterEqual(fresh.written_time_mark, _STARTED)
        self.assertGreater(len(winners), 1, "jedna odpověď vyhrála všechny souběhy")

    def test_failed_transaction_rolls_back_the_choice_and_the_result(self) -> None:
        exam, question, answer = self._started_answer(True)
        before = self._snapshot(exam.id)

        def fail(session, _exam, _moment, *, minimum_step):
            session.flush()
            raise sqlite3.OperationalError("simulovaná chyba transakce")

        with patch.object(written_exam_service, "_apply_time_mark", fail):
            with self.assertRaises(sqlite3.OperationalError):
                written_exam_service.save_choice(
                    exam.id,
                    question.exam_question_id,
                    answer.id,
                    now=_STARTED + timedelta(seconds=5),
                )
        self.assertEqual(written_exam_service.choices(exam.id), [])
        self.assertEqual(self._snapshot(exam.id), before)

        def fail_score(session, _exam, _now):
            session.flush()
            raise sqlite3.OperationalError("simulovaná chyba vyhodnocení")

        with patch.object(written_exam_service, "_record_written_result", fail_score):
            with self.assertRaises(sqlite3.OperationalError):
                written_exam_service.submit(
                    exam.id,
                    now=_STARTED + timedelta(seconds=6),
                )
        self.assertEqual(self._snapshot(exam.id), before)
        self.assertEqual(test_exam_service.get_exam(exam.id).status, EXAM_STATUS_STARTED)

    def _started_answer(self, correct: bool):
        exam = _prepare(self.employee.id, self.test.id)
        written_exam_service.start(exam.id, now=_STARTED)
        question = written_exam_service.screen(exam.id).questions[0]
        answer = self._picked_answer(question.exam_question_id, correct)
        return exam, question, answer

    def _picked_answer(self, exam_question_id: int, correct: bool):
        answers = test_exam_service.get_written_answers(exam_question_id)
        return next(item for item in answers if bool(item.is_correct) is correct)

    def _other_answer(self, exam_question_id: int, answer_id: int):
        answers = test_exam_service.get_written_answers(exam_question_id)
        return next(item for item in answers if item.id != answer_id)

    def _race(self, first, second) -> dict:
        barrier = threading.Barrier(2)
        box: dict = {}

        def run(name, function):
            barrier.wait(timeout=5)
            try:
                box[name] = ("ok", function())
            except Exception as exc:
                box[name] = ("err", exc)

        threads = [
            threading.Thread(target=run, args=("a", first)),
            threading.Thread(target=run, args=("b", second)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive(), "souběžná operace se nezavřela")
        self.assertIn("a", box)
        self.assertIn("b", box)
        return box

    def _assert_no_lock(self, outcome: dict) -> None:
        for name, item in outcome.items():
            if item[0] != "err":
                continue
            text = str(item[1]).lower()
            self.assertNotIn("locked", text, f"{name}: {item[1]!r}")

    def _assert_counted(self, exam_id: int, answer_id: int, correct: bool) -> None:
        exam = test_exam_service.get_exam(exam_id)
        assert exam is not None
        self.assertEqual(exam.status, EXAM_STATUS_COMPLETED)
        stored = written_exam_service.choices(exam_id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].exam_answer_id, answer_id)
        if correct:
            self.assertEqual(exam.written_correct_count, 1)
            self.assertEqual(exam.written_incorrect_count, 0)
            self.assertEqual(exam.written_result, WRITTEN_RESULT_PASSED)
        else:
            self.assertEqual(exam.written_correct_count, 0)
            self.assertEqual(exam.written_incorrect_count, 1)
            self.assertEqual(exam.written_result, WRITTEN_RESULT_FAILED)
        self.assertEqual(exam.written_unanswered_count, 0)

    def _assert_unanswered(self, exam_id: int) -> None:
        exam = test_exam_service.get_exam(exam_id)
        assert exam is not None
        self.assertEqual(exam.status, EXAM_STATUS_COMPLETED)
        self.assertEqual(written_exam_service.choices(exam_id), [])
        self.assertEqual(exam.written_correct_count, 0)
        self.assertEqual(exam.written_unanswered_count, 1)
        self.assertEqual(exam.written_result, WRITTEN_RESULT_FAILED)

    def _snapshot(self, exam_id: int):
        exam = test_exam_service.get_exam(exam_id)
        assert exam is not None
        return (
            exam.status,
            exam.written_finish_reason,
            exam.written_finished_at,
            exam.written_result,
            exam.written_correct_count,
            exam.written_incorrect_count,
            exam.written_unanswered_count,
            exam.written_evaluated_at,
            exam.written_time_mark,
            exam.written_started_at,
            [
                (choice.exam_answer_id, choice.selected_letter, choice.saved_at)
                for choice in written_exam_service.choices(exam_id)
            ],
        )
