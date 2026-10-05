"""Banka písemných otázek. Služba není závislá na Qt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.models.attachment_staging import (
    AttachmentStagingError,
    AttachmentStagingState,
    PreparedAttachmentChanges,
)
from core.services.attachment_service import attachment_service
from core.database.session import get_session
from moduly.testy.constants import ANSWER_KIND_IMAGE, ANSWER_KIND_TEXT, ANSWER_LETTERS
from moduly.testy.modely.written_question import WrittenQuestion
from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer
from moduly.testy.repository.written_question_repository import WrittenQuestionRepository
from moduly.testy.sluzby.written_question_topic_service import (
    written_question_topic_service,
)

ENTITY_QUESTION_IMAGE = "test_written_question"
ENTITY_ANSWER_IMAGE = "test_written_answer"
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"})


class WrittenQuestionError(ValueError):
    pass


@dataclass
class WrittenAnswerInput:
    """Jedna odpověď A/B/C před uložením.

    Textový režim používá ``text``. Obrázkový režim buď ``image_source_path``
    (nový soubor, zkopíruje se až při uložení), nebo ``image_attachment_id``
    (ponechat už uložený obrázek).
    """

    text: str = ""
    image_source_path: str | None = None
    image_attachment_id: int | None = None
    is_correct: bool = False


class WrittenQuestionService:
    def __init__(self) -> None:
        self.repository = WrittenQuestionRepository()

    def create_question(
        self,
        *,
        topic_id: int | None,
        text: str,
        answer_kind: str,
        answers: list[WrittenAnswerInput],
        question_image_source_path: str | None = None,
        question_image_attachment_id: int | None = None,
        note: str = "",
        active: bool = True,
    ) -> WrittenQuestion:
        return self._save(
            None,
            topic_id=topic_id,
            text=text,
            answer_kind=answer_kind,
            answers=answers,
            question_image_source_path=question_image_source_path,
            question_image_attachment_id=question_image_attachment_id,
            note=note,
            active=active,
        )

    def update_question(
        self,
        question_id: int,
        *,
        topic_id: int | None,
        text: str,
        answer_kind: str,
        answers: list[WrittenAnswerInput],
        question_image_source_path: str | None = None,
        question_image_attachment_id: int | None = None,
        note: str = "",
        active: bool = True,
    ) -> WrittenQuestion:
        return self._save(
            question_id,
            topic_id=topic_id,
            text=text,
            answer_kind=answer_kind,
            answers=answers,
            question_image_source_path=question_image_source_path,
            question_image_attachment_id=question_image_attachment_id,
            note=note,
            active=active,
        )

    def get_question(self, question_id: int | None) -> WrittenQuestion | None:
        if not question_id:
            return None
        return self.repository.get_by_id(question_id)

    def get_answers(self, question_id: int) -> list[WrittenQuestionAnswer]:
        self._require_question(question_id)
        return self.repository.get_answers(question_id)

    def list_questions(
        self,
        *,
        include_inactive: bool = False,
        topic_id: int | None = None,
    ) -> list[WrittenQuestion]:
        return self.repository.get_all(
            include_inactive=include_inactive,
            topic_id=topic_id,
        )

    def set_active(self, question_id: int, *, active: bool) -> WrittenQuestion:
        question = self._require_question(question_id)
        question.active = bool(active)
        question.updated_at = datetime.now()
        session = get_session()
        try:
            question = session.merge(question)
            session.commit()
            session.refresh(question)
            session.expunge(question)
            return question
        finally:
            session.close()

    def deactivate(self, question_id: int) -> WrittenQuestion:
        return self.set_active(question_id, active=False)

    def activate(self, question_id: int) -> WrittenQuestion:
        return self.set_active(question_id, active=True)

    def attachment_path(self, attachment_id: int | None) -> Path | None:
        if not attachment_id:
            return None
        record = attachment_service.repository.get_by_id(int(attachment_id))
        if record is None:
            return None
        path = attachment_service.resolve_path(record)
        return path if path.is_file() else None

    def _save(
        self,
        question_id: int | None,
        *,
        topic_id: int | None,
        text: str,
        answer_kind: str,
        answers: list[WrittenAnswerInput],
        question_image_source_path: str | None,
        question_image_attachment_id: int | None,
        note: str,
        active: bool,
    ) -> WrittenQuestion:
        existing = self._require_question(question_id) if question_id else None
        topic = self._require_topic(topic_id, existing)
        stored_text = self._validate_text(text)
        kind = self._validate_kind(answer_kind)
        normalized_answers = self._validate_answers(kind, answers)
        image_source = self._validate_optional_image(
            question_image_source_path,
            "Obrázek otázky",
        )
        stored_note = str(note or "").strip()

        session = get_session()
        session.expire_on_commit = False
        prepared: list[PreparedAttachmentChanges] = []
        try:
            if existing is None:
                question = WrittenQuestion(
                    topic_id=topic.id,
                    text=stored_text,
                    answer_kind=kind,
                    note=stored_note,
                    active=bool(active),
                )
                session.add(question)
                session.flush()
                rows = [
                    WrittenQuestionAnswer(
                        question_id=question.id,
                        position=position,
                        text="",
                        is_correct=False,
                    )
                    for position in range(1, 4)
                ]
                session.add_all(rows)
                session.flush()
            else:
                question = session.get(WrittenQuestion, existing.id)
                if question is None:
                    raise WrittenQuestionError("Otázka nebyla nalezena.")
                question.topic_id = topic.id
                question.text = stored_text
                question.answer_kind = kind
                question.note = stored_note
                question.active = bool(active)
                question.updated_at = datetime.now()
                rows = self._locked_answers(session, question.id)

            question.image_attachment_id, image_change = self._sync_image(
                session,
                entity_type=ENTITY_QUESTION_IMAGE,
                entity_id=question.id,
                current_attachment_id=question.image_attachment_id,
                source_path=image_source,
                keep_attachment_id=question_image_attachment_id,
            )
            if image_change is not None:
                prepared.append(image_change)

            for row, incoming in zip(rows, normalized_answers, strict=True):
                row.text = incoming.text
                row.is_correct = incoming.is_correct
                if kind == ANSWER_KIND_TEXT:
                    row.image_attachment_id, change = self._sync_image(
                        session,
                        entity_type=ENTITY_ANSWER_IMAGE,
                        entity_id=row.id,
                        current_attachment_id=row.image_attachment_id,
                        source_path=None,
                        keep_attachment_id=None,
                    )
                else:
                    row.image_attachment_id, change = self._sync_image(
                        session,
                        entity_type=ENTITY_ANSWER_IMAGE,
                        entity_id=row.id,
                        current_attachment_id=row.image_attachment_id,
                        source_path=incoming.image_source_path,
                        keep_attachment_id=incoming.image_attachment_id,
                    )
                if change is not None:
                    prepared.append(change)

            session.commit()
            session.refresh(question)
            session.expunge(question)
        except WrittenQuestionError:
            session.rollback()
            self._rollback_prepared(prepared)
            raise
        except AttachmentStagingError as exc:
            session.rollback()
            self._rollback_prepared(prepared)
            raise WrittenQuestionError(str(exc)) from exc
        except Exception:
            session.rollback()
            self._rollback_prepared(prepared)
            raise
        else:
            for change in prepared:
                attachment_service.finalize_attachment_changes(change)
            return question
        finally:
            session.close()

    def _sync_image(
        self,
        session,
        *,
        entity_type: str,
        entity_id: int,
        current_attachment_id: int | None,
        source_path: str | None,
        keep_attachment_id: int | None,
    ) -> tuple[int | None, PreparedAttachmentChanges | None]:
        if source_path:
            staging = AttachmentStagingState()
            if current_attachment_id:
                staging.mark_for_removal(int(current_attachment_id))
            staging.add_pending_path(source_path)
            prepared = attachment_service.prepare_attachment_staging(
                entity_type,
                entity_id,
                staging,
                session,
            )
            created = prepared.created_attachments[0]
            return int(created.id), prepared

        if keep_attachment_id:
            if int(keep_attachment_id) != int(current_attachment_id or 0):
                raise WrittenQuestionError("Uložený obrázek k otázce nepatří.")
            return int(keep_attachment_id), None

        if not current_attachment_id:
            return None, None

        staging = AttachmentStagingState()
        staging.mark_for_removal(int(current_attachment_id))
        prepared = attachment_service.prepare_attachment_staging(
            entity_type,
            entity_id,
            staging,
            session,
        )
        return None, prepared

    def _rollback_prepared(self, prepared: list[PreparedAttachmentChanges]) -> None:
        for change in prepared:
            try:
                attachment_service.rollback_attachment_changes(change)
            except Exception:
                continue

    def _locked_answers(self, session, question_id: int) -> list[WrittenQuestionAnswer]:
        from sqlalchemy import select

        stmt = (
            select(WrittenQuestionAnswer)
            .where(WrittenQuestionAnswer.question_id == int(question_id))
            .order_by(WrittenQuestionAnswer.position, WrittenQuestionAnswer.id)
        )
        rows = list(session.scalars(stmt))
        if len(rows) != 3 or [row.position for row in rows] != [1, 2, 3]:
            raise WrittenQuestionError("Otázka nemá právě 3 odpovědi.")
        return rows

    def _require_question(self, question_id: int | None) -> WrittenQuestion:
        question = self.repository.get_by_id(int(question_id or 0))
        if question is None:
            raise WrittenQuestionError("Otázka nebyla nalezena.")
        return question

    def _require_topic(self, topic_id: int | None, existing: WrittenQuestion | None):
        if not topic_id:
            raise WrittenQuestionError("Zvolte okruh.")
        topic = written_question_topic_service.get_topic(int(topic_id))
        if topic is None:
            raise WrittenQuestionError("Zvolený okruh neexistuje.")
        same_inactive = (
            existing is not None
            and int(existing.topic_id) == int(topic.id)
            and not topic.active
        )
        if not topic.active and not same_inactive:
            raise WrittenQuestionError(
                "Novou otázku nebo jiný okruh lze zvolit jen z aktivních okruhů."
            )
        return topic

    def _validate_text(self, text: str) -> str:
        stored = str(text or "").strip()
        if not stored:
            raise WrittenQuestionError("Vyplňte text otázky.")
        return stored

    def _validate_kind(self, answer_kind: str) -> str:
        kind = str(answer_kind or "").strip()
        if kind not in {ANSWER_KIND_TEXT, ANSWER_KIND_IMAGE}:
            raise WrittenQuestionError("Zvolte typ odpovědí.")
        return kind

    def _validate_answers(
        self,
        kind: str,
        answers: list[WrittenAnswerInput],
    ) -> list[WrittenAnswerInput]:
        if len(answers) != 3:
            raise WrittenQuestionError("Otázka musí mít právě 3 odpovědi.")
        correct = sum(1 for answer in answers if answer.is_correct)
        if correct != 1:
            raise WrittenQuestionError("Označte právě jednu správnou odpověď.")

        normalized: list[WrittenAnswerInput] = []
        for index, answer in enumerate(answers):
            letter = ANSWER_LETTERS[index]
            text = " ".join(str(answer.text or "").split())
            source = self._validate_optional_image(
                answer.image_source_path,
                f"Obrázek odpovědi {letter}",
            )
            keep_id = answer.image_attachment_id
            has_image = bool(source or keep_id)
            has_text = bool(text)
            if kind == ANSWER_KIND_TEXT:
                if has_image:
                    raise WrittenQuestionError(
                        "Textové a obrázkové odpovědi nelze kombinovat."
                    )
                if not has_text:
                    raise WrittenQuestionError(f"Vyplňte text odpovědi {letter}.")
                normalized.append(
                    WrittenAnswerInput(text=text, is_correct=answer.is_correct)
                )
                continue
            if has_text:
                raise WrittenQuestionError(
                    "Textové a obrázkové odpovědi nelze kombinovat."
                )
            if not has_image:
                raise WrittenQuestionError(f"Vyberte obrázek odpovědi {letter}.")
            normalized.append(
                WrittenAnswerInput(
                    image_source_path=source,
                    image_attachment_id=int(keep_id) if keep_id and not source else None,
                    is_correct=answer.is_correct,
                )
            )
        return normalized

    def _validate_optional_image(self, path: str | None, label: str) -> str | None:
        text = str(path or "").strip()
        if not text:
            return None
        file_path = Path(text)
        if not file_path.is_file():
            raise WrittenQuestionError(f"{label} se nepodařilo načíst.")
        if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise WrittenQuestionError(f"{label} není podporovaný obrázek.")
        return str(file_path)


written_question_service = WrittenQuestionService()
