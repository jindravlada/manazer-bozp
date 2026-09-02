"""Katalog kontrolních orgánů a pracovišť — bez Qt."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from moduly.statni_dozor.constants import (
    AUTHORITY_CODE_DUPLICATE_MESSAGE,
    AUTHORITY_CODE_REQUIRED_MESSAGE,
    AUTHORITY_DISPLAY_ORDER_INVALID_MESSAGE,
    AUTHORITY_EXTERNAL_KEY_DUPLICATE_MESSAGE,
    AUTHORITY_HAS_ACTIVE_OFFICES_MESSAGE,
    AUTHORITY_IMPORT_ORIGINS,
    AUTHORITY_NAME_REQUIRED_MESSAGE,
    AUTHORITY_NOT_FOUND_MESSAGE,
    AUTHORITY_ORIGIN_INVALID_MESSAGE,
    AUTHORITY_ORIGIN_MANUAL,
    OFFICE_ACTIVE_UNDER_INACTIVE_AUTHORITY_MESSAGE,
    OFFICE_AUTHORITY_REQUIRED_MESSAGE,
    OFFICE_DISPLAY_ORDER_INVALID_MESSAGE,
    OFFICE_EXTERNAL_KEY_DUPLICATE_MESSAGE,
    OFFICE_KIND_INVALID_MESSAGE,
    OFFICE_KINDS,
    OFFICE_NAME_REQUIRED_MESSAGE,
    OFFICE_NOT_FOUND_MESSAGE,
    OFFICE_ORIGIN_INVALID_MESSAGE,
)
from moduly.statni_dozor.modely.control_authority import ControlAuthority
from moduly.statni_dozor.modely.control_authority_office import ControlAuthorityOffice
from moduly.statni_dozor.repository.control_authority_catalog_repository import (
    ControlAuthorityCatalogRepository,
)


class ControlAuthorityCatalogError(ValueError):
    """Validační chyba katalogu kontrolních orgánů."""


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _canonicalize_code(value: Any) -> str:
    raw = str(value or "").strip().lower()
    code = re.sub(r"\s+", "-", raw)
    if not code:
        raise ControlAuthorityCatalogError(AUTHORITY_CODE_REQUIRED_MESSAGE)
    return code


def slugify_authority_code(name: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(name or ""))
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.casefold()).strip("-")
    return slug or "organ"


def _require_name(value: Any, message: str) -> str:
    name = str(value or "").strip()
    if not name:
        raise ControlAuthorityCatalogError(message)
    return name


def _require_display_order(value: Any, message: str) -> int:
    try:
        order = int(value)
    except (TypeError, ValueError) as exc:
        raise ControlAuthorityCatalogError(message) from exc
    if order < 0:
        raise ControlAuthorityCatalogError(message)
    return order


def _require_origin(value: Any, *, allowed: frozenset[str], message: str) -> str:
    origin = str(value or "").strip()
    if origin not in allowed:
        raise ControlAuthorityCatalogError(message)
    return origin


def _optional_office_kind(value: Any) -> str | None:
    kind = _blank_to_none(value)
    if kind is None:
        return None
    if kind not in OFFICE_KINDS:
        raise ControlAuthorityCatalogError(OFFICE_KIND_INVALID_MESSAGE)
    return kind


class ControlAuthorityCatalogService:
    def __init__(self, repository: ControlAuthorityCatalogRepository | None = None):
        self.repository = repository or ControlAuthorityCatalogRepository()

    def list_authorities(
        self,
        include_inactive: bool = False,
        query: str | None = None,
        *,
        session: Session | None = None,
    ) -> list[ControlAuthority]:
        return self.repository.list_authorities(
            include_inactive=include_inactive,
            query=query,
            session=session,
        )

    def get_authority(
        self,
        authority_id: int,
        *,
        session: Session | None = None,
    ) -> ControlAuthority | None:
        return self.repository.get_authority(int(authority_id), session=session)

    def allocate_unique_authority_code(
        self,
        name: str,
        *,
        session: Session | None = None,
    ) -> str:
        try:
            base = _canonicalize_code(slugify_authority_code(name))
        except ControlAuthorityCatalogError:
            base = "organ"
        candidate = base
        suffix = 2
        while self.get_authority_by_code(candidate, session=session) is not None:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def get_authority_by_code(
        self,
        code: str,
        *,
        session: Session | None = None,
    ) -> ControlAuthority | None:
        try:
            canonical = _canonicalize_code(code)
        except ControlAuthorityCatalogError:
            return None
        return self.repository.get_authority_by_code(canonical, session=session)

    def get_authority_by_external_key(
        self,
        external_key: str,
        *,
        session: Session | None = None,
    ) -> ControlAuthority | None:
        key = _blank_to_none(external_key)
        if key is None:
            return None
        return self.repository.get_authority_by_external_key(key, session=session)

    def create_authority(
        self,
        *,
        code: str,
        name: str,
        abbreviation: str | None = None,
        website: str | None = None,
        active: bool = True,
        display_order: int = 0,
        external_key: str | None = None,
        source_url: str | None = None,
        session: Session | None = None,
    ) -> ControlAuthority:
        return self._create_authority(
            code=code,
            name=name,
            abbreviation=abbreviation,
            website=website,
            active=active,
            display_order=display_order,
            external_key=external_key,
            source_url=source_url,
            from_import=False,
            session=session,
        )

    def create_imported_authority(
        self,
        *,
        code: str,
        name: str,
        origin: str,
        abbreviation: str | None = None,
        website: str | None = None,
        active: bool = True,
        display_order: int = 0,
        external_key: str | None = None,
        source_url: str | None = None,
        last_checked_at: datetime | None = None,
        session: Session | None = None,
    ) -> ControlAuthority:
        return self._create_authority(
            code=code,
            name=name,
            abbreviation=abbreviation,
            website=website,
            active=active,
            display_order=display_order,
            origin=origin,
            external_key=external_key,
            source_url=source_url,
            last_checked_at=last_checked_at,
            from_import=True,
            session=session,
        )

    def update_authority(
        self,
        authority_id: int,
        *,
        code: str | None = None,
        name: str | None = None,
        abbreviation: str | None = None,
        website: str | None = None,
        display_order: int | None = None,
        external_key: str | None = None,
        source_url: str | None = None,
        session: Session | None = None,
    ) -> ControlAuthority:
        return self._update_authority(
            authority_id,
            code=code,
            name=name,
            abbreviation=abbreviation,
            website=website,
            display_order=display_order,
            external_key=external_key,
            source_url=source_url,
            from_import=False,
            session=session,
        )

    def update_imported_authority(
        self,
        authority_id: int,
        *,
        code: str | None = None,
        name: str | None = None,
        origin: str | None = None,
        abbreviation: str | None = None,
        website: str | None = None,
        display_order: int | None = None,
        external_key: str | None = None,
        source_url: str | None = None,
        last_checked_at: datetime | None = None,
        session: Session | None = None,
    ) -> ControlAuthority:
        return self._update_authority(
            authority_id,
            code=code,
            name=name,
            origin=origin,
            abbreviation=abbreviation,
            website=website,
            display_order=display_order,
            external_key=external_key,
            source_url=source_url,
            last_checked_at=last_checked_at,
            from_import=True,
            session=session,
        )

    def deactivate_authority(
        self,
        authority_id: int,
        *,
        session: Session | None = None,
    ) -> ControlAuthority:
        with self.repository.session(session) as (sess, owns):
            record = self._require_authority(authority_id, session=sess)
            active_offices = self.repository.count_active_offices(
                int(authority_id), session=sess
            )
            if active_offices:
                raise ControlAuthorityCatalogError(
                    AUTHORITY_HAS_ACTIVE_OFFICES_MESSAGE
                )
            record.active = False
            record.user_edited_at = datetime.now()
            record.updated_at = datetime.now()
            saved = self.repository.update_authority(record, session=sess)
            if owns:
                sess.commit()
                sess.refresh(saved)
                sess.expunge(saved)
            return saved

    def reactivate_authority(
        self,
        authority_id: int,
        *,
        session: Session | None = None,
    ) -> ControlAuthority:
        with self.repository.session(session) as (sess, owns):
            record = self._require_authority(authority_id, session=sess)
            record.active = True
            record.user_edited_at = datetime.now()
            record.updated_at = datetime.now()
            saved = self.repository.update_authority(record, session=sess)
            if owns:
                sess.commit()
                sess.refresh(saved)
                sess.expunge(saved)
            return saved

    def list_offices(
        self,
        authority_id: int | None = None,
        include_inactive: bool = False,
        query: str | None = None,
        *,
        session: Session | None = None,
    ) -> list[ControlAuthorityOffice]:
        return self.repository.list_offices(
            authority_id=authority_id,
            include_inactive=include_inactive,
            query=query,
            session=session,
        )

    def get_office(
        self,
        office_id: int,
        *,
        session: Session | None = None,
    ) -> ControlAuthorityOffice | None:
        return self.repository.get_office(int(office_id), session=session)

    def get_office_by_external_key(
        self,
        external_key: str,
        *,
        session: Session | None = None,
    ) -> ControlAuthorityOffice | None:
        key = _blank_to_none(external_key)
        if key is None:
            return None
        return self.repository.get_office_by_external_key(key, session=session)

    def create_office(
        self,
        *,
        authority_id: int,
        name: str,
        abbreviation: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        website: str | None = None,
        territorial_scope: str | None = None,
        office_kind: str | None = None,
        active: bool = True,
        display_order: int = 0,
        external_key: str | None = None,
        source_url: str | None = None,
        session: Session | None = None,
    ) -> ControlAuthorityOffice:
        return self._create_office(
            authority_id=authority_id,
            name=name,
            abbreviation=abbreviation,
            address=address,
            phone=phone,
            email=email,
            website=website,
            territorial_scope=territorial_scope,
            office_kind=office_kind,
            active=active,
            display_order=display_order,
            external_key=external_key,
            source_url=source_url,
            from_import=False,
            session=session,
        )

    def create_imported_office(
        self,
        *,
        authority_id: int,
        name: str,
        origin: str,
        abbreviation: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        website: str | None = None,
        territorial_scope: str | None = None,
        office_kind: str | None = None,
        active: bool = True,
        display_order: int = 0,
        external_key: str | None = None,
        source_url: str | None = None,
        last_checked_at: datetime | None = None,
        session: Session | None = None,
    ) -> ControlAuthorityOffice:
        return self._create_office(
            authority_id=authority_id,
            name=name,
            origin=origin,
            abbreviation=abbreviation,
            address=address,
            phone=phone,
            email=email,
            website=website,
            territorial_scope=territorial_scope,
            office_kind=office_kind,
            active=active,
            display_order=display_order,
            external_key=external_key,
            source_url=source_url,
            last_checked_at=last_checked_at,
            from_import=True,
            session=session,
        )

    def update_office(
        self,
        office_id: int,
        *,
        authority_id: int | None = None,
        name: str | None = None,
        abbreviation: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        website: str | None = None,
        territorial_scope: str | None = None,
        office_kind: str | None = None,
        display_order: int | None = None,
        external_key: str | None = None,
        source_url: str | None = None,
        session: Session | None = None,
    ) -> ControlAuthorityOffice:
        return self._update_office(
            office_id,
            authority_id=authority_id,
            name=name,
            abbreviation=abbreviation,
            address=address,
            phone=phone,
            email=email,
            website=website,
            territorial_scope=territorial_scope,
            office_kind=office_kind,
            display_order=display_order,
            external_key=external_key,
            source_url=source_url,
            from_import=False,
            session=session,
        )

    def update_imported_office(
        self,
        office_id: int,
        *,
        authority_id: int | None = None,
        name: str | None = None,
        origin: str | None = None,
        abbreviation: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        website: str | None = None,
        territorial_scope: str | None = None,
        office_kind: str | None = None,
        display_order: int | None = None,
        external_key: str | None = None,
        source_url: str | None = None,
        last_checked_at: datetime | None = None,
        session: Session | None = None,
    ) -> ControlAuthorityOffice:
        return self._update_office(
            office_id,
            authority_id=authority_id,
            name=name,
            origin=origin,
            abbreviation=abbreviation,
            address=address,
            phone=phone,
            email=email,
            website=website,
            territorial_scope=territorial_scope,
            office_kind=office_kind,
            display_order=display_order,
            external_key=external_key,
            source_url=source_url,
            last_checked_at=last_checked_at,
            from_import=True,
            session=session,
        )

    def deactivate_office(
        self,
        office_id: int,
        *,
        session: Session | None = None,
    ) -> ControlAuthorityOffice:
        with self.repository.session(session) as (sess, owns):
            record = self._require_office(office_id, session=sess)
            record.active = False
            record.user_edited_at = datetime.now()
            record.updated_at = datetime.now()
            saved = self.repository.update_office(record, session=sess)
            if owns:
                sess.commit()
                sess.refresh(saved)
                sess.expunge(saved)
            return saved

    def reactivate_office(
        self,
        office_id: int,
        *,
        session: Session | None = None,
    ) -> ControlAuthorityOffice:
        with self.repository.session(session) as (sess, owns):
            record = self._require_office(office_id, session=sess)
            parent = self._require_authority(int(record.authority_id), session=sess)
            if not parent.active:
                raise ControlAuthorityCatalogError(
                    OFFICE_ACTIVE_UNDER_INACTIVE_AUTHORITY_MESSAGE
                )
            record.active = True
            record.user_edited_at = datetime.now()
            record.updated_at = datetime.now()
            saved = self.repository.update_office(record, session=sess)
            if owns:
                sess.commit()
                sess.refresh(saved)
                sess.expunge(saved)
            return saved

    def _create_authority(
        self,
        *,
        code: str,
        name: str,
        abbreviation: str | None,
        website: str | None,
        active: bool,
        display_order: int,
        external_key: str | None,
        source_url: str | None,
        from_import: bool,
        origin: str | None = None,
        last_checked_at: datetime | None = None,
        session: Session | None = None,
    ) -> ControlAuthority:
        canonical = _canonicalize_code(code)
        clean_name = _require_name(name, AUTHORITY_NAME_REQUIRED_MESSAGE)
        order = _require_display_order(
            display_order, AUTHORITY_DISPLAY_ORDER_INVALID_MESSAGE
        )
        key = _blank_to_none(external_key)
        if from_import:
            origin_value = _require_origin(
                origin,
                allowed=AUTHORITY_IMPORT_ORIGINS,
                message=AUTHORITY_ORIGIN_INVALID_MESSAGE,
            )
            user_edited_at = None
            checked_at = last_checked_at
        else:
            origin_value = AUTHORITY_ORIGIN_MANUAL
            user_edited_at = datetime.now()
            checked_at = None
        with self.repository.session(session) as (sess, owns):
            self._assert_unique_authority_code(canonical, session=sess)
            self._assert_unique_authority_external_key(key, session=sess)
            record = ControlAuthority(
                code=canonical,
                name=clean_name,
                abbreviation=_blank_to_none(abbreviation),
                website=_blank_to_none(website),
                active=bool(active),
                display_order=order,
                origin=origin_value,
                external_key=key,
                source_url=_blank_to_none(source_url),
                last_checked_at=checked_at,
                user_edited_at=user_edited_at,
            )
            try:
                saved = self.repository.add_authority(record, session=sess)
            except IntegrityError as exc:
                raise ControlAuthorityCatalogError(
                    AUTHORITY_CODE_DUPLICATE_MESSAGE
                ) from exc
            if owns:
                sess.commit()
                sess.refresh(saved)
                sess.expunge(saved)
            return saved

    def _update_authority(
        self,
        authority_id: int,
        *,
        code: str | None,
        name: str | None,
        abbreviation: str | None,
        website: str | None,
        display_order: int | None,
        external_key: str | None,
        source_url: str | None,
        from_import: bool,
        origin: str | None = None,
        last_checked_at: datetime | None = None,
        session: Session | None = None,
    ) -> ControlAuthority:
        with self.repository.session(session) as (sess, owns):
            record = self._require_authority(authority_id, session=sess)
            if code is not None:
                canonical = _canonicalize_code(code)
                self._assert_unique_authority_code(
                    canonical, exclude_id=record.id, session=sess
                )
                record.code = canonical
            if name is not None:
                record.name = _require_name(name, AUTHORITY_NAME_REQUIRED_MESSAGE)
            if abbreviation is not None:
                record.abbreviation = _blank_to_none(abbreviation)
            if website is not None:
                record.website = _blank_to_none(website)
            if display_order is not None:
                record.display_order = _require_display_order(
                    display_order, AUTHORITY_DISPLAY_ORDER_INVALID_MESSAGE
                )
            if external_key is not None:
                key = _blank_to_none(external_key)
                self._assert_unique_authority_external_key(
                    key, exclude_id=record.id, session=sess
                )
                record.external_key = key
            if source_url is not None:
                record.source_url = _blank_to_none(source_url)
            if from_import:
                if origin is not None:
                    record.origin = _require_origin(
                        origin,
                        allowed=AUTHORITY_IMPORT_ORIGINS,
                        message=AUTHORITY_ORIGIN_INVALID_MESSAGE,
                    )
                if last_checked_at is not None:
                    record.last_checked_at = last_checked_at
            else:
                record.origin = AUTHORITY_ORIGIN_MANUAL
                record.user_edited_at = datetime.now()
            record.updated_at = datetime.now()
            try:
                saved = self.repository.update_authority(record, session=sess)
            except IntegrityError as exc:
                raise ControlAuthorityCatalogError(
                    AUTHORITY_CODE_DUPLICATE_MESSAGE
                ) from exc
            if owns:
                sess.commit()
                sess.refresh(saved)
                sess.expunge(saved)
            return saved

    def _create_office(
        self,
        *,
        authority_id: int,
        name: str,
        abbreviation: str | None,
        address: str | None,
        phone: str | None,
        email: str | None,
        website: str | None,
        territorial_scope: str | None,
        office_kind: str | None,
        active: bool,
        display_order: int,
        external_key: str | None,
        source_url: str | None,
        from_import: bool,
        origin: str | None = None,
        last_checked_at: datetime | None = None,
        session: Session | None = None,
    ) -> ControlAuthorityOffice:
        if not authority_id:
            raise ControlAuthorityCatalogError(OFFICE_AUTHORITY_REQUIRED_MESSAGE)
        clean_name = _require_name(name, OFFICE_NAME_REQUIRED_MESSAGE)
        order = _require_display_order(
            display_order, OFFICE_DISPLAY_ORDER_INVALID_MESSAGE
        )
        kind = _optional_office_kind(office_kind)
        key = _blank_to_none(external_key)
        if from_import:
            origin_value = _require_origin(
                origin,
                allowed=AUTHORITY_IMPORT_ORIGINS,
                message=OFFICE_ORIGIN_INVALID_MESSAGE,
            )
            user_edited_at = None
            checked_at = last_checked_at
        else:
            origin_value = AUTHORITY_ORIGIN_MANUAL
            user_edited_at = datetime.now()
            checked_at = None
        with self.repository.session(session) as (sess, owns):
            parent = self._require_authority(int(authority_id), session=sess)
            if bool(active) and not parent.active:
                raise ControlAuthorityCatalogError(
                    OFFICE_ACTIVE_UNDER_INACTIVE_AUTHORITY_MESSAGE
                )
            self._assert_unique_office_external_key(key, session=sess)
            record = ControlAuthorityOffice(
                authority_id=int(authority_id),
                name=clean_name,
                abbreviation=_blank_to_none(abbreviation),
                address=_blank_to_none(address),
                phone=_blank_to_none(phone),
                email=_blank_to_none(email),
                website=_blank_to_none(website),
                territorial_scope=_blank_to_none(territorial_scope),
                office_kind=kind,
                active=bool(active),
                display_order=order,
                origin=origin_value,
                external_key=key,
                source_url=_blank_to_none(source_url),
                last_checked_at=checked_at,
                user_edited_at=user_edited_at,
            )
            try:
                saved = self.repository.add_office(record, session=sess)
            except IntegrityError as exc:
                raise ControlAuthorityCatalogError(
                    OFFICE_EXTERNAL_KEY_DUPLICATE_MESSAGE
                ) from exc
            if owns:
                sess.commit()
                sess.refresh(saved)
                sess.expunge(saved)
            return saved

    def _update_office(
        self,
        office_id: int,
        *,
        authority_id: int | None,
        name: str | None,
        abbreviation: str | None,
        address: str | None,
        phone: str | None,
        email: str | None,
        website: str | None,
        territorial_scope: str | None,
        office_kind: str | None,
        display_order: int | None,
        external_key: str | None,
        source_url: str | None,
        from_import: bool,
        origin: str | None = None,
        last_checked_at: datetime | None = None,
        session: Session | None = None,
    ) -> ControlAuthorityOffice:
        with self.repository.session(session) as (sess, owns):
            record = self._require_office(office_id, session=sess)
            parent_id = int(authority_id) if authority_id is not None else int(
                record.authority_id
            )
            parent = self._require_authority(parent_id, session=sess)
            if record.active and not parent.active:
                raise ControlAuthorityCatalogError(
                    OFFICE_ACTIVE_UNDER_INACTIVE_AUTHORITY_MESSAGE
                )
            record.authority_id = parent_id
            if name is not None:
                record.name = _require_name(name, OFFICE_NAME_REQUIRED_MESSAGE)
            if abbreviation is not None:
                record.abbreviation = _blank_to_none(abbreviation)
            if address is not None:
                record.address = _blank_to_none(address)
            if phone is not None:
                record.phone = _blank_to_none(phone)
            if email is not None:
                record.email = _blank_to_none(email)
            if website is not None:
                record.website = _blank_to_none(website)
            if territorial_scope is not None:
                record.territorial_scope = _blank_to_none(territorial_scope)
            if office_kind is not None:
                record.office_kind = _optional_office_kind(office_kind)
            if display_order is not None:
                record.display_order = _require_display_order(
                    display_order, OFFICE_DISPLAY_ORDER_INVALID_MESSAGE
                )
            if external_key is not None:
                key = _blank_to_none(external_key)
                self._assert_unique_office_external_key(
                    key, exclude_id=record.id, session=sess
                )
                record.external_key = key
            if source_url is not None:
                record.source_url = _blank_to_none(source_url)
            if from_import:
                if origin is not None:
                    record.origin = _require_origin(
                        origin,
                        allowed=AUTHORITY_IMPORT_ORIGINS,
                        message=OFFICE_ORIGIN_INVALID_MESSAGE,
                    )
                if last_checked_at is not None:
                    record.last_checked_at = last_checked_at
            else:
                record.origin = AUTHORITY_ORIGIN_MANUAL
                record.user_edited_at = datetime.now()
            record.updated_at = datetime.now()
            try:
                saved = self.repository.update_office(record, session=sess)
            except IntegrityError as exc:
                raise ControlAuthorityCatalogError(
                    OFFICE_EXTERNAL_KEY_DUPLICATE_MESSAGE
                ) from exc
            if owns:
                sess.commit()
                sess.refresh(saved)
                sess.expunge(saved)
            return saved

    def _require_authority(
        self,
        authority_id: int,
        *,
        session: Session,
    ) -> ControlAuthority:
        record = self.repository.get_authority(int(authority_id), session=session)
        if record is None:
            raise ControlAuthorityCatalogError(AUTHORITY_NOT_FOUND_MESSAGE)
        return record

    def _require_office(
        self,
        office_id: int,
        *,
        session: Session,
    ) -> ControlAuthorityOffice:
        record = self.repository.get_office(int(office_id), session=session)
        if record is None:
            raise ControlAuthorityCatalogError(OFFICE_NOT_FOUND_MESSAGE)
        return record

    def _assert_unique_authority_code(
        self,
        code: str,
        *,
        exclude_id: int | None = None,
        session: Session,
    ) -> None:
        existing = self.repository.get_authority_by_code(code, session=session)
        if existing is not None and existing.id != exclude_id:
            raise ControlAuthorityCatalogError(AUTHORITY_CODE_DUPLICATE_MESSAGE)

    def _assert_unique_authority_external_key(
        self,
        external_key: str | None,
        *,
        exclude_id: int | None = None,
        session: Session,
    ) -> None:
        if external_key is None:
            return
        existing = self.repository.get_authority_by_external_key(
            external_key, session=session
        )
        if existing is not None and existing.id != exclude_id:
            raise ControlAuthorityCatalogError(AUTHORITY_EXTERNAL_KEY_DUPLICATE_MESSAGE)

    def _assert_unique_office_external_key(
        self,
        external_key: str | None,
        *,
        exclude_id: int | None = None,
        session: Session,
    ) -> None:
        if external_key is None:
            return
        existing = self.repository.get_office_by_external_key(
            external_key, session=session
        )
        if existing is not None and existing.id != exclude_id:
            raise ControlAuthorityCatalogError(OFFICE_EXTERNAL_KEY_DUPLICATE_MESSAGE)


control_authority_catalog_service = ControlAuthorityCatalogService()
