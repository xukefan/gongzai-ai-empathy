"""Fact-only aggregation for shared weekly, monthly, and anniversary recaps."""

from collections import Counter
from datetime import date, datetime, time, timedelta
from typing import Iterable

from models import Moment


VALID_RECAP_PERIODS = {"week", "month", "anniversary"}


def moment_time(moment: Moment) -> datetime:
    """Use the user-recorded time when available, otherwise creation time."""
    return moment.recorded_at or moment.created_at


def resolve_recap_period(period: str, anchor: date | None) -> tuple[datetime | None, datetime | None, date]:
    """Return an inclusive/exclusive time window and its reference date."""
    reference = anchor or date.today()
    if period == "week":
        start_day = reference - timedelta(days=reference.weekday())
        end_day = start_day + timedelta(days=7)
        return datetime.combine(start_day, time.min), datetime.combine(end_day, time.min), reference
    if period == "month":
        start_day = reference.replace(day=1)
        end_day = (start_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        return datetime.combine(start_day, time.min), datetime.combine(end_day, time.min), reference
    if period == "anniversary":
        if anchor is None:
            raise ValueError("anniversary requires anchor_date")
        return None, None, reference
    raise ValueError("unsupported recap period")


def select_recap_moments(
    period: str,
    moments: Iterable[Moment],
    anchor: date | None,
) -> tuple[list[Moment], datetime | None, datetime | None, date]:
    """Choose only stored source moments; no content is synthesized here."""
    start_at, end_at, reference = resolve_recap_period(period, anchor)
    all_moments = list(moments)
    if period == "anniversary":
        selected = [
            moment for moment in all_moments
            if moment_time(moment).month == reference.month and moment_time(moment).day == reference.day
        ]
    else:
        selected = [
            moment for moment in all_moments
            if start_at <= moment_time(moment) < end_at
        ]
    selected.sort(key=lambda moment: (moment_time(moment), moment.id), reverse=True)
    return selected, start_at, end_at, reference


def build_recap(period: str, moments: Iterable[Moment], anchor: date | None = None) -> dict:
    """Build a traceable recap from confirmed, shared database records only."""
    selected, start_at, end_at, reference = select_recap_moments(period, moments, anchor)
    event_dates = sorted({moment_time(moment).date().isoformat() for moment in selected})
    tag_counts = Counter(
        tag.strip() for moment in selected for tag in (moment.tags or []) if isinstance(tag, str) and tag.strip()
    )
    topics = [
        {"tag": tag, "count": count}
        for tag, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]
    source_events = [
        {
            "id": moment.id,
            "event_id": moment.event_id,
            "title": moment.title,
            "summary": moment.summary,
            "recorded_at": moment_time(moment).isoformat(),
            "tags": moment.tags or [],
        }
        for moment in selected[:3]
    ]
    label = {
        "week": "本周",
        "month": "本月",
        "anniversary": f"每年{reference.month}月{reference.day}日",
    }[period]
    summary = f"{label}共保存 {len(selected)} 条已确认的共同记录，分布在 {len(event_dates)} 天。"
    if topics:
        summary += "明确标签包括：" + "、".join(
            f"{topic['tag']}（{topic['count']}）" for topic in topics[:5]
        ) + "。"
    else:
        summary += "没有可统计的明确标签。"
    return {
        "period": period,
        "anchor_date": reference.isoformat(),
        "period_start": start_at.isoformat() if start_at else None,
        "period_end": end_at.isoformat() if end_at else None,
        "total_moments": len(selected),
        "recorded_dates": event_dates,
        "topics": topics,
        "fact_summary": summary,
        "representative_events": source_events,
        "source_event_ids": [moment.event_id for moment in selected if moment.event_id],
        "generation_method": "deterministic_fact_aggregation",
        "schema_version": 1,
    }
