"""Centrální detekce shodných a textově podobných záznamů (SIMILARITY-1).

Obecná služba bez vazby na konkrétní modul. V první fázi ji používají
kontrolní otázky (kontrolní body) metodiky prověrek; později ji lze napojit
např. na PBP, auditní tvrzení, opatření, rizika nebo právní požadavky.

Algoritmus: normalizace textu + ``difflib.SequenceMatcher`` (včetně token-set
varianty). Bez AI, embeddingů a externích API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

# Prahy podobnosti (0–1). Pod DISPLAY se výsledek nevrací.
SIMILARITY_THRESHOLD_EXACT = 1.0
SIMILARITY_THRESHOLD_VERY_SIMILAR = 0.90
SIMILARITY_THRESHOLD_POSSIBLE = 0.80
SIMILARITY_THRESHOLD_DISPLAY = SIMILARITY_THRESHOLD_POSSIBLE

MATCH_TYPE_EXACT = "exact"
MATCH_TYPE_VERY_SIMILAR = "very_similar"
MATCH_TYPE_POSSIBLE = "possible"

MATCH_TYPE_LABELS = {
    MATCH_TYPE_EXACT: "Přesná shoda",
    MATCH_TYPE_VERY_SIMILAR: "Velmi podobné",
    MATCH_TYPE_POSSIBLE: "Možná podobnost",
}

_TRAILING_PUNCT_RE = re.compile(r"[\s\.\,\;\:\!\?\…]+$", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


@dataclass(frozen=True)
class SimilarityCandidate:
    """Kandidát na porovnání – identifikátor a zobrazovaný text."""

    id: str
    text: str


@dataclass(frozen=True)
class SimilarityMatch:
    """Výsledek porovnání s jedním kandidátem."""

    id: str
    text: str
    match_type: str
    score: float

    @property
    def match_label(self) -> str:
        return MATCH_TYPE_LABELS.get(self.match_type, self.match_type)

    @property
    def score_percent(self) -> int:
        return int(round(self.score * 100))


def normalize_similarity_text(text: str) -> str:
    """Normalizovaná podoba textu pro porovnání (původní text se nemění).

    - trim,
    - malá písmena (casefold),
    - sjednocení mezer a zalomení řádků,
    - odstranění běžné koncové interpunkce.

    Diakritika zůstává zachována.
    """
    value = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = _WHITESPACE_RE.sub(" ", value).strip()
    value = value.casefold()
    value = _TRAILING_PUNCT_RE.sub("", value).strip()
    return value


def _sequence_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _token_set_ratio(left: str, right: str) -> float:
    """Lehká token-set podobnost (inspirace fuzzywuzzy, bez nové závislosti)."""
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0

    intersection = left_tokens & right_tokens
    left_only = left_tokens - right_tokens
    right_only = right_tokens - left_tokens
    sorted_sect = " ".join(sorted(intersection))
    combined_left = f"{sorted_sect} {' '.join(sorted(left_only))}".strip()
    combined_right = f"{sorted_sect} {' '.join(sorted(right_only))}".strip()

    scores = [_sequence_ratio(left, right), _sequence_ratio(combined_left, combined_right)]
    if sorted_sect:
        scores.append(_sequence_ratio(sorted_sect, combined_left))
        scores.append(_sequence_ratio(sorted_sect, combined_right))
    return max(scores)


def similarity_score(left: str, right: str) -> float:
    """Skóre podobnosti dvou již normalizovaných textů (0–1)."""
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return max(_sequence_ratio(left, right), _token_set_ratio(left, right))


def classify_similarity(score: float) -> str | None:
    """Vrátí typ shody, nebo ``None`` pokud je skóre pod prahem zobrazení."""
    if score >= SIMILARITY_THRESHOLD_EXACT:
        return MATCH_TYPE_EXACT
    if score >= SIMILARITY_THRESHOLD_VERY_SIMILAR:
        return MATCH_TYPE_VERY_SIMILAR
    if score >= SIMILARITY_THRESHOLD_POSSIBLE:
        return MATCH_TYPE_POSSIBLE
    return None


def find_similar_texts(
    query_text: str,
    candidates: Iterable[SimilarityCandidate],
    *,
    exclude_ids: Iterable[str] | None = None,
) -> list[SimilarityMatch]:
    """Najde kandidáty podobné ``query_text``.

    Výsledky jsou seřazené od nejvyšší podobnosti. Záznamy s ID v
    ``exclude_ids`` se přeskočí (např. právě editovaný záznam).
    """
    normalized_query = normalize_similarity_text(query_text)
    if not normalized_query:
        return []

    excluded = {str(item) for item in (exclude_ids or []) if str(item)}
    matches: list[SimilarityMatch] = []

    for candidate in candidates:
        candidate_id = str(candidate.id or "").strip()
        if not candidate_id or candidate_id in excluded:
            continue

        original_text = candidate.text if candidate.text is not None else ""
        normalized_candidate = normalize_similarity_text(original_text)
        if not normalized_candidate:
            continue

        score = similarity_score(normalized_query, normalized_candidate)
        match_type = classify_similarity(score)
        if match_type is None:
            continue

        matches.append(
            SimilarityMatch(
                id=candidate_id,
                text=original_text,
                match_type=match_type,
                score=score,
            )
        )

    matches.sort(key=lambda item: (-item.score, item.text.casefold(), item.id))
    return matches


@dataclass(frozen=True)
class SimilarityPair:
    """Jedna kandidátní dvojice podobných textů."""

    left_id: str
    left_text: str
    right_id: str
    right_text: str
    score: float
    match_type: str

    @property
    def match_label(self) -> str:
        return MATCH_TYPE_LABELS.get(self.match_type, self.match_type)

    @property
    def score_percent(self) -> int:
        return int(round(self.score * 100))


def find_similar_pairs(
    candidates: Iterable[SimilarityCandidate],
    *,
    progress_callback=None,
    should_cancel=None,
) -> tuple[list[SimilarityPair], bool]:
    """Hromadné párové porovnání kandidátů (SIMILARITY-2).

    Každá dvojice se vyhodnotí nejvýše jednou. Vrátí ``(páry, cancelled)``.
    ``progress_callback(current, total, found)`` se volá po dokončení každého
    „levého“ záznamu.
    """
    items = [
        candidate
        for candidate in candidates
        if str(candidate.id or "").strip()
        and normalize_similarity_text(candidate.text or "")
    ]
    normalized = [normalize_similarity_text(item.text or "") for item in items]
    total = len(items)
    pairs: list[SimilarityPair] = []
    cancelled = False

    for index, left in enumerate(items):
        if should_cancel is not None and should_cancel():
            cancelled = True
            break

        left_norm = normalized[index]
        for right_index in range(index + 1, total):
            if should_cancel is not None and should_cancel():
                cancelled = True
                break
            score = similarity_score(left_norm, normalized[right_index])
            match_type = classify_similarity(score)
            if match_type is None:
                continue
            right = items[right_index]
            pairs.append(
                SimilarityPair(
                    left_id=str(left.id),
                    left_text=left.text if left.text is not None else "",
                    right_id=str(right.id),
                    right_text=right.text if right.text is not None else "",
                    score=score,
                    match_type=match_type,
                )
            )
        if cancelled:
            break
        if progress_callback is not None:
            progress_callback(index + 1, total, len(pairs))

    pairs.sort(
        key=lambda item: (
            -item.score,
            item.left_text.casefold(),
            item.right_text.casefold(),
            item.left_id,
            item.right_id,
        )
    )
    return pairs, cancelled


class TextSimilarityService:
    """Fasáda pro centrální textovou podobnost."""

    normalize = staticmethod(normalize_similarity_text)
    score = staticmethod(similarity_score)
    classify = staticmethod(classify_similarity)
    find_similar = staticmethod(find_similar_texts)
    find_pairs = staticmethod(find_similar_pairs)


text_similarity_service = TextSimilarityService()
