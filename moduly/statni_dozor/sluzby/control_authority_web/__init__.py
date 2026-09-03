"""Read-only webové adaptéry katalogu kontrolních orgánů."""

from moduly.statni_dozor.sluzby.control_authority_web.catalog_snapshot_service import (
    ControlAuthorityCatalogSnapshotService,
    control_authority_catalog_snapshot_service,
)
from moduly.statni_dozor.sluzby.control_authority_web.cbu_adapter import (
    fetch_cbu_offices,
    parse_cbu_office_html,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff import (
    diff_control_authority_offices,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
    ControlAuthorityOfficeDiff,
    ControlAuthorityOfficeFieldChange,
    ControlAuthorityWebDiffError,
    ControlAuthorityWebDiffResult,
)
from moduly.statni_dozor.sluzby.control_authority_web.du_adapter import (
    fetch_du_offices,
    parse_du_offices_html,
)
from moduly.statni_dozor.sluzby.control_authority_web.http_client import (
    ControlAuthorityHttpClient,
    ControlAuthorityHttpResponse,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
    ControlAuthorityWebAdapterError,
    ControlAuthorityWebFetchResult,
)
from moduly.statni_dozor.sluzby.control_authority_web.suip_adapter import (
    fetch_suip_offices,
    parse_suip_hub_html,
    parse_suip_office_html,
)

__all__ = [
    "ControlAuthorityCatalogSnapshotService",
    "ControlAuthorityHttpClient",
    "ControlAuthorityHttpResponse",
    "ControlAuthorityOfficeCatalogSnapshot",
    "ControlAuthorityOfficeDiff",
    "ControlAuthorityOfficeFieldChange",
    "ControlAuthorityOfficeWebRecord",
    "ControlAuthorityWebAdapterError",
    "ControlAuthorityWebDiffError",
    "ControlAuthorityWebDiffResult",
    "ControlAuthorityWebFetchResult",
    "control_authority_catalog_snapshot_service",
    "diff_control_authority_offices",
    "fetch_cbu_offices",
    "fetch_du_offices",
    "fetch_suip_offices",
    "parse_cbu_office_html",
    "parse_du_offices_html",
    "parse_suip_hub_html",
    "parse_suip_office_html",
]
