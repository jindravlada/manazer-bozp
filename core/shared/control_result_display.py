from core.shared.constants import (
    CONTROL_RESULT_LABELS,
    CONTROL_RESULT_NEKONTROLOVANO,
    CONTROL_RESULT_NELZE_POSOUDIT,
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_VYHOVUJE,
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
    VALID_CONTROL_RESULTS,
)

CONTROL_RESULT_OPTIONS = tuple(
    (value, CONTROL_RESULT_LABELS[value])
    for value in (
        CONTROL_RESULT_NEKONTROLOVANO,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_NELZE_POSOUDIT,
    )
)


def control_result_label(result: str) -> str:
    return CONTROL_RESULT_LABELS.get(result, result or "—")


def allows_finding(result: str) -> bool:
    return result == CONTROL_RESULT_NEVYHOVUJE


def allows_pkz_action(result: str) -> bool:
    return result == CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM


def allows_create_finding(result: str) -> bool:
    return allows_finding(result) or allows_pkz_action(result)


def protocol_evaluation_results() -> frozenset[str]:
    return frozenset(
        {
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            CONTROL_RESULT_NEVYHOVUJE,
        }
    )


def is_valid_control_result(result: str) -> bool:
    return result in VALID_CONTROL_RESULTS
