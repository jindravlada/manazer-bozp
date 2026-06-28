import shutil
from pathlib import Path

from core.models.attachment import Attachment
from core.repositories.attachment_repository import AttachmentRepository
from core.services.storage_service import storage_service


class AttachmentService:
    def __init__(self):
        self.repository = AttachmentRepository()

    def get_for_entity(self, entity_type: str, entity_id: int):
        if not entity_id:
            return []
        return self.repository.get_for_entity(entity_type, entity_id)

    def add_file(self, entity_type: str, entity_id: int, source_path: str):
        source = Path(source_path)
        return self.add_file_as(entity_type, entity_id, source_path, source.name)

    def add_file_as(self, entity_type: str, entity_id: int, source_path: str, target_filename: str):
        source = Path(source_path)

        if not source.exists() or not entity_id:
            return None

        target_dir = storage_service.attachment_dir(entity_type, entity_id)
        target = self._unique_target(target_dir / target_filename)

        shutil.copy2(source, target)

        relative_path = target.relative_to(storage_service.attachments_dir)

        attachment = Attachment(
            entity_type=entity_type,
            entity_id=entity_id,
            original_path=str(source),
            stored_path=str(relative_path),
            filename=target.name,
        )

        return self.repository.add(attachment)

    def resolve_path(self, attachment) -> Path:
        stored = Path(attachment.stored_path)

        if stored.is_absolute():
            return stored

        return storage_service.attachment_absolute(attachment.stored_path)

    def delete(self, attachment_id: int):
        return self.repository.delete(attachment_id)

    def _unique_target(self, target: Path) -> Path:
        if not target.exists():
            return target

        counter = 2

        while True:
            candidate = target.with_name(f"{target.stem}_{counter}{target.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1


attachment_service = AttachmentService()
