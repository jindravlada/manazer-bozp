"""Read-only webové adaptéry katalogu kontrolních orgánů."""

from moduly.statni_dozor.sluzby.control_authority_web.apply import (
    ControlAuthorityOfficeWebApplySelection,
    ControlAuthorityWebApplyError,
    ControlAuthorityWebApplyResult,
    ControlAuthorityWebApplyService,
    apply_authority_web_changes,
)
from moduly.statni_dozor.sluzby.control_authority_web.catalog_snapshot_service import (
    ControlAuthorityCatalogSnapshotService,
    control_authority_catalog_snapshot_service,
)
from moduly.statni_dozor.sluzby.control_authority_web.cbu_adapter import (
    fetch_cbu_offices,
    parse_cbu_office_html,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    ControlAuthorityWebAdapterInfo,
    ControlAuthorityWebAdapterRegistration,
    ControlAuthorityWebCheckError,
    ControlAuthorityWebCheckResult,
    ControlAuthorityWebCheckService,
    build_web_adapter_registry,
    check_authority_web,
    check_authority_web_coverage,
    get_web_adapter_info,
    get_web_adapter_info_by_coverage,
    has_web_adapter,
    list_web_adapter_infos,
    supported_authority_codes,
)
from moduly.statni_dozor.sluzby.control_authority_web.coverage import (
    ControlAuthorityWebCoverage,
    ControlAuthorityWebCoverageError,
    cbu_web_coverage,
    coverage_for_authority,
    du_web_coverage,
    hzs_web_coverage,
    khs_web_coverage,
    suip_web_coverage,
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
from moduly.statni_dozor.sluzby.control_authority_web.hzs_adapter import (
    fetch_hzs_offices,
    parse_hzs_offices_html,
)
from moduly.statni_dozor.sluzby.control_authority_web.khs_adapter import (
    fetch_khs_offices,
    parse_khs_offices_html,
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
    "ControlAuthorityOfficeWebApplySelection",
    "ControlAuthorityOfficeWebRecord",
    "ControlAuthorityWebAdapterError",
    "ControlAuthorityWebAdapterInfo",
    "ControlAuthorityWebAdapterRegistration",
    "ControlAuthorityWebApplyError",
    "ControlAuthorityWebApplyResult",
    "ControlAuthorityWebApplyService",
    "ControlAuthorityWebCheckError",
    "ControlAuthorityWebCheckResult",
    "ControlAuthorityWebCheckService",
    "ControlAuthorityWebCoverage",
    "ControlAuthorityWebCoverageError",
    "ControlAuthorityWebDiffError",
    "ControlAuthorityWebDiffResult",
    "ControlAuthorityWebFetchResult",
    "apply_authority_web_changes",
    "build_web_adapter_registry",
    "check_authority_web",
    "check_authority_web_coverage",
    "control_authority_catalog_snapshot_service",
    "coverage_for_authority",
    "cbu_web_coverage",
    "diff_control_authority_offices",
    "du_web_coverage",
    "fetch_cbu_offices",
    "fetch_du_offices",
    "fetch_hzs_offices",
    "fetch_khs_offices",
    "fetch_suip_offices",
    "get_web_adapter_info",
    "get_web_adapter_info_by_coverage",
    "has_web_adapter",
    "hzs_web_coverage",
    "khs_web_coverage",
    "list_web_adapter_infos",
    "hzs_web_coverage",
    "khs_web_coverage",
    "parse_cbu_office_html",
    "parse_du_offices_html",
    "parse_hzs_offices_html",
    "parse_khs_offices_html",
    "parse_suip_hub_html",
    "parse_suip_office_html",
    "suip_web_coverage",
    "supported_authority_codes",
]
