"""Read-only webové adaptéry katalogu kontrolních orgánů."""

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

__all__ = [
    "ControlAuthorityHttpClient",
    "ControlAuthorityHttpResponse",
    "ControlAuthorityOfficeWebRecord",
    "ControlAuthorityWebAdapterError",
    "ControlAuthorityWebFetchResult",
    "fetch_du_offices",
    "parse_du_offices_html",
]
