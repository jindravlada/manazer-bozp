"""Read-only načtení katalogových snapshotů pracovišť."""

from __future__ import annotations

from moduly.statni_dozor.constants import WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND
from moduly.statni_dozor.repository.control_authority_catalog_repository import (
    ControlAuthorityCatalogRepository,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff import (
    diff_control_authority_offices,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
    ControlAuthorityWebDiffResult,
    diff_error,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityWebFetchResult,
)


def snapshot_from_office(office, authority_code: str) -> ControlAuthorityOfficeCatalogSnapshot:
    return ControlAuthorityOfficeCatalogSnapshot(
        id=int(office.id),
        authority_id=int(office.authority_id),
        authority_code=str(authority_code),
        external_key=office.external_key,
        name=str(office.name),
        address=office.address,
        phone=office.phone,
        email=office.email,
        website=office.website,
        territorial_scope=office.territorial_scope,
        office_kind=office.office_kind,
        source_url=office.source_url,
        active=bool(office.active),
        origin=str(office.origin),
        user_edited_at=office.user_edited_at,
        last_checked_at=office.last_checked_at,
    )


class ControlAuthorityCatalogSnapshotService:
    """Načte pracoviště orgánu jednou dávkou a ihned zavře session."""

    def __init__(self, repository: ControlAuthorityCatalogRepository | None = None):
        self.repository = repository or ControlAuthorityCatalogRepository()

    def load_office_snapshots(
        self,
        authority_code: str,
    ) -> tuple[ControlAuthorityOfficeCatalogSnapshot, ...]:
        code = str(authority_code or "").strip().casefold()
        if not code:
            raise diff_error(WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND)
        with self.repository.session() as (sess, _owns):
            authority = self.repository.get_authority_by_code(code, session=sess)
            if authority is None:
                raise diff_error(WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND)
            offices = self.repository.list_offices(
                authority_id=int(authority.id),
                include_inactive=True,
                session=sess,
            )
            return tuple(
                snapshot_from_office(office, authority.code) for office in offices
            )

    def compare_web_result(
        self,
        fetch_result: ControlAuthorityWebFetchResult,
        *,
        authority_code: str | None = None,
    ) -> ControlAuthorityWebDiffResult:
        snapshots = self.load_office_snapshots(
            authority_code or fetch_result.authority_code
        )
        return diff_control_authority_offices(fetch_result, snapshots)


control_authority_catalog_snapshot_service = ControlAuthorityCatalogSnapshotService()
