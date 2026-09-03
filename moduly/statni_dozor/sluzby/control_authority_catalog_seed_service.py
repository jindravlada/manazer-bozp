"""Idempotentní import výchozího katalogu kontrolních orgánů (SEED-8A1)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from core.database.upgrade_guard import MigrationGuardError
from core.paths import project_root as resolve_project_root
from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_ADDRESS_REQUIRED_MESSAGE,
    AUTHORITY_CATALOG_SEED_COLLISION_MESSAGE,
    AUTHORITY_CATALOG_SEED_DUPLICATE_CODE_MESSAGE,
    AUTHORITY_CATALOG_SEED_DUPLICATE_KEY_MESSAGE,
    AUTHORITY_CATALOG_SEED_KEY_REQUIRED_MESSAGE,
    AUTHORITY_CATALOG_SEED_ICO_FORBIDDEN_MESSAGE,
    AUTHORITY_CATALOG_SEED_MANUAL_DUPLICATE_SKIP_MESSAGE,
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    AUTHORITY_CATALOG_SEED_SCHEMA_INVALID_MESSAGE,
    AUTHORITY_CATALOG_SEED_SCHEMA_VERSION,
    AUTHORITY_CATALOG_SEED_STARTUP_MESSAGE,
    AUTHORITY_CATALOG_SEED_URL_INVALID_MESSAGE,
    AUTHORITY_DISPLAY_ORDER_INVALID_MESSAGE,
    AUTHORITY_NAME_REQUIRED_MESSAGE,
    AUTHORITY_ORIGIN_BUNDLED,
    AUTHORITY_ORIGIN_INVALID_MESSAGE,
    AUTHORITY_ORIGIN_MANUAL,
    OFFICE_DISPLAY_ORDER_INVALID_MESSAGE,
    OFFICE_KIND_INVALID_MESSAGE,
    OFFICE_KINDS,
    OFFICE_NAME_REQUIRED_MESSAGE,
    OFFICE_ORIGIN_INVALID_MESSAGE,
)
from moduly.statni_dozor.modely.control_authority import ControlAuthority
from moduly.statni_dozor.modely.control_authority_office import ControlAuthorityOffice
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    ControlAuthorityCatalogError,
    ControlAuthorityCatalogService,
    _blank_to_none,
    _canonicalize_code,
    _optional_office_kind,
    _require_display_order,
    _require_name,
    _require_origin,
    control_authority_catalog_service,
)

logger = logging.getLogger(__name__)

FORBIDDEN_ICO_KEYS = frozenset(
    {
        "ico",
        "ičo",
        "ic",
        "dic",
        "vat_id",
        "identification_number",
        "authority_ico",
        "office_ico",
        "ico_o",
        "ic_number",
    }
)


class ControlAuthorityCatalogSeedError(ControlAuthorityCatalogError, MigrationGuardError):
    """Neplatný nebo kolidující bundled seed katalogu."""


@dataclass(frozen=True)
class SeedImportResult:
    catalog_version: str | None
    authorities_created: int
    offices_created: int
    authorities_skipped: int
    offices_skipped: int
    committed: bool
    skipped_reason: str | None = None


def bundled_catalog_path() -> Path:
    return resolve_project_root() / AUTHORITY_CATALOG_SEED_RELATIVE_PATH


def _normalize_catalog_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _startup_error(detail: str) -> ControlAuthorityCatalogSeedError:
    logger.error("Katalog kontrolních orgánů: %s", detail)
    return ControlAuthorityCatalogSeedError(
        f"{AUTHORITY_CATALOG_SEED_STARTUP_MESSAGE}\n\nDetail: {detail}"
    )


def _catalog_tables_ready(*, session: Session | None = None) -> bool:
    from sqlalchemy import inspect as sa_inspect

    from core.database.session import engine, reconfigure_database_engine

    if session is not None:
        inspector = sa_inspect(session.get_bind())
    else:
        reconfigure_database_engine()
        inspector = sa_inspect(engine)
    tables = set(inspector.get_table_names())
    return "control_authorities" in tables and "control_authority_offices" in tables


def _walk_forbidden_ico(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).strip().lower()
            if key_text in FORBIDDEN_ICO_KEYS:
                raise ControlAuthorityCatalogSeedError(
                    AUTHORITY_CATALOG_SEED_ICO_FORBIDDEN_MESSAGE
                )
            _walk_forbidden_ico(nested, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_forbidden_ico(nested, path=f"{path}[{index}]")


def _require_https_url(value: Any, *, required: bool) -> str | None:
    text = _blank_to_none(value)
    if text is None:
        if required:
            raise ControlAuthorityCatalogSeedError(
                AUTHORITY_CATALOG_SEED_URL_INVALID_MESSAGE
            )
        return None
    parsed = urlparse(text)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ControlAuthorityCatalogSeedError(
            AUTHORITY_CATALOG_SEED_URL_INVALID_MESSAGE
        )
    return text


def _require_external_key(value: Any) -> str:
    key = _blank_to_none(value)
    if key is None:
        raise ControlAuthorityCatalogSeedError(
            AUTHORITY_CATALOG_SEED_KEY_REQUIRED_MESSAGE
        )
    return key


def load_catalog_json(path: Path | None = None) -> dict[str, Any]:
    catalog_path = Path(path) if path is not None else bundled_catalog_path()
    try:
        raw = catalog_path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except FileNotFoundError as exc:
        raise _startup_error(f"Soubor katalogu chybí: {catalog_path}") from exc
    except OSError as exc:
        raise _startup_error(f"Soubor katalogu nelze přečíst: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise _startup_error(f"Soubor katalogu není platný JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise _startup_error("Kořen katalogu musí být objekt.")
    return payload


def validate_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    _walk_forbidden_ico(payload)
    try:
        schema_version = int(payload.get("schema_version"))
    except (TypeError, ValueError) as exc:
        raise ControlAuthorityCatalogSeedError(
            AUTHORITY_CATALOG_SEED_SCHEMA_INVALID_MESSAGE
        ) from exc
    if schema_version != AUTHORITY_CATALOG_SEED_SCHEMA_VERSION:
        raise ControlAuthorityCatalogSeedError(
            AUTHORITY_CATALOG_SEED_SCHEMA_INVALID_MESSAGE
        )

    catalog_version = _blank_to_none(payload.get("catalog_version"))
    if catalog_version is None:
        raise ControlAuthorityCatalogSeedError("Chybí catalog_version.")
    verified_at = _blank_to_none(payload.get("verified_at"))
    if verified_at is None:
        raise ControlAuthorityCatalogSeedError("Chybí verified_at.")

    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ControlAuthorityCatalogSeedError("Chybí seznam oficiálních zdrojů.")
    for source in sources:
        if not isinstance(source, dict):
            raise ControlAuthorityCatalogSeedError("Položka sources musí být objekt.")
        _require_https_url(source.get("url"), required=True)
        if _blank_to_none(source.get("title")) is None:
            raise ControlAuthorityCatalogSeedError("Zdroj musí mít název.")

    authorities = payload.get("authorities")
    if not isinstance(authorities, list) or not authorities:
        raise ControlAuthorityCatalogSeedError("Chybí seznam kontrolních orgánů.")

    seen_codes: set[str] = set()
    seen_keys: set[str] = set()
    seen_authority_orders: set[int] = set()
    validated_authorities: list[dict[str, Any]] = []
    for authority in authorities:
        if not isinstance(authority, dict):
            raise ControlAuthorityCatalogSeedError("Orgán musí být objekt.")
        code = _canonicalize_code(authority.get("code"))
        if code in seen_codes:
            raise ControlAuthorityCatalogSeedError(
                AUTHORITY_CATALOG_SEED_DUPLICATE_CODE_MESSAGE
            )
        seen_codes.add(code)
        auth_key = _require_external_key(authority.get("external_key"))
        if auth_key in seen_keys:
            raise ControlAuthorityCatalogSeedError(
                AUTHORITY_CATALOG_SEED_DUPLICATE_KEY_MESSAGE
            )
        seen_keys.add(auth_key)
        origin = _require_origin(
            authority.get("origin") or AUTHORITY_ORIGIN_BUNDLED,
            allowed=frozenset({AUTHORITY_ORIGIN_BUNDLED}),
            message=AUTHORITY_ORIGIN_INVALID_MESSAGE,
        )
        authority_order = _require_display_order(
            authority.get("display_order", 0),
            AUTHORITY_DISPLAY_ORDER_INVALID_MESSAGE,
        )
        if authority_order in seen_authority_orders:
            raise ControlAuthorityCatalogSeedError(
                AUTHORITY_DISPLAY_ORDER_INVALID_MESSAGE
            )
        seen_authority_orders.add(authority_order)
        offices_raw = authority.get("offices")
        if not isinstance(offices_raw, list) or not offices_raw:
            raise ControlAuthorityCatalogSeedError(
                "Kontrolní orgán musí mít alespoň jedno pracoviště."
            )
        offices: list[dict[str, Any]] = []
        for office in offices_raw:
            if not isinstance(office, dict):
                raise ControlAuthorityCatalogSeedError("Pracoviště musí být objekt.")
            office_key = _require_external_key(office.get("external_key"))
            if office_key in seen_keys:
                raise ControlAuthorityCatalogSeedError(
                    AUTHORITY_CATALOG_SEED_DUPLICATE_KEY_MESSAGE
                )
            seen_keys.add(office_key)
            address = _blank_to_none(office.get("address"))
            if address is None:
                raise ControlAuthorityCatalogSeedError(
                    AUTHORITY_CATALOG_SEED_ADDRESS_REQUIRED_MESSAGE
                )
            office_origin = _require_origin(
                office.get("origin") or AUTHORITY_ORIGIN_BUNDLED,
                allowed=frozenset({AUTHORITY_ORIGIN_BUNDLED}),
                message=OFFICE_ORIGIN_INVALID_MESSAGE,
            )
            kind = _optional_office_kind(office.get("office_kind"))
            if kind is None:
                raise ControlAuthorityCatalogSeedError(OFFICE_KIND_INVALID_MESSAGE)
            if kind not in OFFICE_KINDS:
                raise ControlAuthorityCatalogSeedError(OFFICE_KIND_INVALID_MESSAGE)
            office_order = _require_display_order(
                office.get("display_order", 0),
                OFFICE_DISPLAY_ORDER_INVALID_MESSAGE,
            )
            offices.append(
                {
                    "external_key": office_key,
                    "name": _require_name(
                        office.get("name"), OFFICE_NAME_REQUIRED_MESSAGE
                    ),
                    "abbreviation": _blank_to_none(office.get("abbreviation")),
                    "address": address,
                    "phone": _blank_to_none(office.get("phone")),
                    "email": _blank_to_none(office.get("email")),
                    "website": _require_https_url(
                        office.get("website"), required=False
                    ),
                    "territorial_scope": _blank_to_none(
                        office.get("territorial_scope")
                    ),
                    "office_kind": kind,
                    "display_order": office_order,
                    "origin": office_origin,
                    "source_url": _require_https_url(
                        office.get("source_url"), required=True
                    ),
                }
            )
        validated_authorities.append(
            {
                "code": code,
                "name": _require_name(
                    authority.get("name"), AUTHORITY_NAME_REQUIRED_MESSAGE
                ),
                "abbreviation": _blank_to_none(authority.get("abbreviation")),
                "website": _require_https_url(
                    authority.get("website"), required=False
                ),
                "display_order": authority_order,
                "origin": origin,
                "external_key": auth_key,
                "source_url": _require_https_url(
                    authority.get("source_url"), required=True
                ),
                "offices": offices,
            }
        )

    return {
        "schema_version": schema_version,
        "catalog_version": catalog_version,
        "verified_at": verified_at,
        "authorities": validated_authorities,
    }


def _is_protected(record: ControlAuthority | ControlAuthorityOffice) -> bool:
    if record.origin == AUTHORITY_ORIGIN_MANUAL:
        return True
    if record.user_edited_at is not None:
        return True
    return False


class ControlAuthorityCatalogSeedService:
    def __init__(self, catalog_service: ControlAuthorityCatalogService | None = None):
        self.catalog_service = catalog_service or control_authority_catalog_service

    def load_bundled(self, path: Path | None = None) -> dict[str, Any]:
        return validate_catalog(load_catalog_json(path))

    def import_catalog(
        self,
        payload: dict[str, Any] | None = None,
        *,
        path: Path | None = None,
        session: Session | None = None,
    ) -> SeedImportResult:
        try:
            catalog = payload if payload is not None else load_catalog_json(path)
            validated = validate_catalog(catalog)
        except ControlAuthorityCatalogSeedError as exc:
            if AUTHORITY_CATALOG_SEED_STARTUP_MESSAGE in str(exc):
                raise
            raise _startup_error(str(exc)) from exc
        except ControlAuthorityCatalogError as exc:
            raise _startup_error(str(exc)) from exc
        if not _catalog_tables_ready(session=session):
            logger.info(
                "Katalog kontrolních orgánů: schéma CORE-8A0 ještě není dostupné."
            )
            return SeedImportResult(
                catalog_version=validated["catalog_version"],
                authorities_created=0,
                offices_created=0,
                authorities_skipped=0,
                offices_skipped=0,
                committed=False,
                skipped_reason="schema_missing",
            )

        with self.catalog_service.repository.session(session) as (sess, owns):
            try:
                plan = self._plan_import(validated, session=sess)
                created_authorities = 0
                created_offices = 0
                for authority_payload in plan["new_authorities"]:
                    self.catalog_service.create_imported_authority(
                        code=authority_payload["code"],
                        name=authority_payload["name"],
                        origin=AUTHORITY_ORIGIN_BUNDLED,
                        abbreviation=authority_payload["abbreviation"],
                        website=authority_payload["website"],
                        display_order=authority_payload["display_order"],
                        external_key=authority_payload["external_key"],
                        source_url=authority_payload["source_url"],
                        last_checked_at=None,
                        session=sess,
                    )
                    created_authorities += 1
                for office_payload in plan["new_offices"]:
                    parent = self._resolve_authority(
                        office_payload["authority_code"],
                        office_payload["authority_external_key"],
                        session=sess,
                    )
                    if parent is None:
                        raise ControlAuthorityCatalogSeedError(
                            OFFICE_NAME_REQUIRED_MESSAGE
                        )
                    self.catalog_service.create_imported_office(
                        authority_id=int(parent.id),
                        name=office_payload["name"],
                        origin=AUTHORITY_ORIGIN_BUNDLED,
                        abbreviation=office_payload["abbreviation"],
                        address=office_payload["address"],
                        phone=office_payload["phone"],
                        email=office_payload["email"],
                        website=office_payload["website"],
                        territorial_scope=office_payload["territorial_scope"],
                        office_kind=office_payload["office_kind"],
                        display_order=office_payload["display_order"],
                        external_key=office_payload["external_key"],
                        source_url=office_payload["source_url"],
                        last_checked_at=None,
                        session=sess,
                    )
                    created_offices += 1
            except ControlAuthorityCatalogError as exc:
                logger.error("Katalog kontrolních orgánů: %s", exc)
                raise ControlAuthorityCatalogSeedError(
                    f"{AUTHORITY_CATALOG_SEED_STARTUP_MESSAGE}\n\nDetail: {exc}"
                ) from exc

            committed = False
            if owns and (created_authorities or created_offices):
                sess.commit()
                committed = True
            return SeedImportResult(
                catalog_version=validated["catalog_version"],
                authorities_created=created_authorities,
                offices_created=created_offices,
                authorities_skipped=plan["authorities_skipped"],
                offices_skipped=plan["offices_skipped"],
                committed=committed,
            )

    def ensure_default_catalog(
        self,
        *,
        path: Path | None = None,
        session: Session | None = None,
    ) -> SeedImportResult:
        if not _catalog_tables_ready(session=session):
            return SeedImportResult(
                catalog_version=None,
                authorities_created=0,
                offices_created=0,
                authorities_skipped=0,
                offices_skipped=0,
                committed=False,
                skipped_reason="schema_missing",
            )
        return self.import_catalog(path=path, session=session)

    def _plan_import(
        self,
        validated: dict[str, Any],
        *,
        session: Session,
    ) -> dict[str, Any]:
        new_authorities: list[dict[str, Any]] = []
        new_offices: list[dict[str, Any]] = []
        authorities_skipped = 0
        offices_skipped = 0

        for authority in validated["authorities"]:
            existing = self._match_authority(authority, session=session)
            if existing is None:
                self._assert_no_key_type_collision(
                    authority["external_key"], expected="authority", session=session
                )
                new_authorities.append(authority)
            else:
                authorities_skipped += 1

            for office in authority["offices"]:
                office_payload = {
                    **office,
                    "authority_code": authority["code"],
                    "authority_external_key": authority["external_key"],
                }
                existing_office = self._match_office(office, session=session)
                if existing_office is None:
                    self._assert_no_key_type_collision(
                        office["external_key"], expected="office", session=session
                    )
                    if existing is not None and not existing.active:
                        offices_skipped += 1
                        continue
                    if existing is not None and self._manual_name_address_duplicate(
                        office, authority_id=int(existing.id), session=session
                    ):
                        logger.warning(
                            AUTHORITY_CATALOG_SEED_MANUAL_DUPLICATE_SKIP_MESSAGE.format(
                                name=office["name"]
                            )
                        )
                        offices_skipped += 1
                        continue
                    new_offices.append(office_payload)
                    continue
                parent_id = int(existing_office.authority_id)
                expected_parent = existing or self._match_authority(
                    authority, session=session
                )
                if expected_parent is not None and parent_id != int(expected_parent.id):
                    raise ControlAuthorityCatalogSeedError(
                        AUTHORITY_CATALOG_SEED_COLLISION_MESSAGE
                    )
                if existing is None:
                    # rodič se teprve vloží; existující office se stejným klíčem
                    # pod jiným orgánem je kolize
                    raise ControlAuthorityCatalogSeedError(
                        AUTHORITY_CATALOG_SEED_COLLISION_MESSAGE
                    )
                offices_skipped += 1

        return {
            "new_authorities": new_authorities,
            "new_offices": new_offices,
            "authorities_skipped": authorities_skipped,
            "offices_skipped": offices_skipped,
        }

    def _match_authority(
        self,
        authority: dict[str, Any],
        *,
        session: Session,
    ) -> ControlAuthority | None:
        by_key = self.catalog_service.get_authority_by_external_key(
            authority["external_key"], session=session
        )
        if by_key is not None:
            self._assert_authority_compatible(by_key, authority)
            return by_key
        by_code = self.catalog_service.get_authority_by_code(
            authority["code"], session=session
        )
        if by_code is not None:
            self._assert_authority_compatible(by_code, authority)
        return by_code

    def _match_office(
        self,
        office: dict[str, Any],
        *,
        session: Session,
    ) -> ControlAuthorityOffice | None:
        existing = self.catalog_service.get_office_by_external_key(
            office["external_key"], session=session
        )
        if existing is not None:
            if _is_protected(existing) or not existing.active:
                return existing
        return existing

    def _manual_name_address_duplicate(
        self,
        office: dict[str, Any],
        *,
        authority_id: int,
        session: Session,
    ) -> ControlAuthorityOffice | None:
        seed_name = _normalize_catalog_text(office.get("name"))
        seed_address = _normalize_catalog_text(office.get("address"))
        if not seed_name or not seed_address:
            return None
        for local in self.catalog_service.list_offices(
            authority_id=authority_id,
            include_inactive=True,
            session=session,
        ):
            if str(local.external_key or "").strip():
                continue
            if _normalize_catalog_text(local.name) != seed_name:
                continue
            if _normalize_catalog_text(local.address) != seed_address:
                continue
            return local
        return None

    def _assert_authority_compatible(
        self,
        existing: ControlAuthority,
        authority: dict[str, Any],
    ) -> None:
        if existing.external_key and existing.external_key != authority["external_key"]:
            if existing.code == authority["code"]:
                return
            raise ControlAuthorityCatalogSeedError(
                AUTHORITY_CATALOG_SEED_COLLISION_MESSAGE
            )

    def _assert_no_key_type_collision(
        self,
        external_key: str,
        *,
        expected: str,
        session: Session,
    ) -> None:
        as_authority = self.catalog_service.get_authority_by_external_key(
            external_key, session=session
        )
        as_office = self.catalog_service.get_office_by_external_key(
            external_key, session=session
        )
        if expected == "authority" and as_office is not None:
            raise ControlAuthorityCatalogSeedError(
                AUTHORITY_CATALOG_SEED_COLLISION_MESSAGE
            )
        if expected == "office" and as_authority is not None:
            raise ControlAuthorityCatalogSeedError(
                AUTHORITY_CATALOG_SEED_COLLISION_MESSAGE
            )

    def _resolve_authority(
        self,
        code: str,
        external_key: str,
        *,
        session: Session,
    ) -> ControlAuthority | None:
        by_key = self.catalog_service.get_authority_by_external_key(
            external_key, session=session
        )
        if by_key is not None:
            return by_key
        return self.catalog_service.get_authority_by_code(code, session=session)


control_authority_catalog_seed_service = ControlAuthorityCatalogSeedService()


def ensure_control_authority_catalog(
    *,
    path: Path | None = None,
    session: Session | None = None,
) -> SeedImportResult:
    return control_authority_catalog_seed_service.ensure_default_catalog(
        path=path,
        session=session,
    )
