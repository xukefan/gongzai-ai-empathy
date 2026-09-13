"""Private, local retrieval over confirmed shared life moments."""

import re
from datetime import datetime
from typing import Iterable

from models import Moment


SEARCH_METHOD = "local_lexical_semantic_v1"
_ASCII_WORDS = re.compile(r"[a-z0-9]+")
_CJK_RUNS = re.compile(r"[\u4e00-\u9fff]+")


def moment_time(moment: Moment) -> datetime:
    return moment.recorded_at or moment.created_at


def normalize(text: str) -> str:
    return "".join(text.lower().split())


def query_terms(query: str) -> list[str]:
    """Derive deterministic terms from keywords or a short natural-language query."""
    normalized = normalize(query)
    terms = set(_ASCII_WORDS.findall(normalized))
    for run in _CJK_RUNS.findall(normalized):
        terms.add(run)
        terms.update(run[index:index + 2] for index in range(len(run) - 1))
        if len(run) == 1:
            terms.add(run)
    return sorted(term for term in terms if term)


def searchable_fields(moment: Moment) -> dict[str, str]:
    return {
        "title": normalize(moment.title or ""),
        "summary": normalize(moment.summary or ""),
        "confirmed_transcript": normalize(moment.confirmed_transcript or ""),
        "tags": normalize(" ".join(tag for tag in (moment.tags or []) if isinstance(tag, str))),
    }


def score_moment(moment: Moment, terms: list[str]) -> tuple[int, list[str]]:
    fields = searchable_fields(moment)
    weights = {"tags": 8, "title": 5, "summary": 3, "confirmed_transcript": 2}
    score = 0
    matched_fields: list[str] = []
    for field, text in fields.items():
        matches = sum(1 for term in terms if term in text)
        if matches:
            score += matches * weights[field]
            matched_fields.append(field)
    return score, matched_fields


def search_memories(query: str, moments: Iterable[Moment], limit: int) -> dict:
    """Rank source records locally; return no model-generated statements."""
    terms = query_terms(query)
    ranked = []
    for moment in moments:
        score, matched_fields = score_moment(moment, terms)
        if score <= 0:
            continue
        ranked.append((score, moment_time(moment), moment, matched_fields))
    ranked.sort(key=lambda item: (item[0], item[1], item[2].id), reverse=True)
    results = [
        {
            "id": moment.id,
            "event_id": moment.event_id,
            "title": moment.title,
            "summary": moment.summary,
            "confirmed_transcript": moment.confirmed_transcript,
            "recorded_at": recorded_at.isoformat(),
            "tags": moment.tags or [],
            "score": score,
            "matched_fields": fields,
        }
        for score, recorded_at, moment, fields in ranked[:limit]
    ]
    return {
        "query": query,
        "query_terms": terms,
        "total": len(results),
        "results": results,
        "search_method": SEARCH_METHOD,
        "schema_version": 1,
    }
