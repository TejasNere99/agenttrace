from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable


class FailureDetector:
    """Find recorded failure signals without inferring an unobserved root cause."""

    def detect(self, events: Iterable[dict[str, Any]], run_status: str | None = None) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for event in events:
            event_id = _event_id(event)
            event_type = _value(event.get("event_type"))
            status = _value(event.get("status"))
            error = event.get("error")
            signals: list[str] = []
            if status == "failed":
                signals.append("status=failed")
            if event_type == "error":
                signals.append("event_type=error")
            if _has_error(error):
                signals.append("structured_error_present")
            error_classification = error.get("classification") if isinstance(error, dict) else None
            if error_classification:
                signals.append(f"error.classification={error_classification}")
            if not signals:
                continue
            dedupe_key = event_id or f"sequence:{event.get('sequence_number')}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            category = _classify(event_type, error)
            records.append({
                "event_id": event_id,
                "sequence_number": event.get("sequence_number"),
                "event_type": event_type,
                "event_name": event.get("name"),
                "timestamp": _iso(event.get("timestamp")),
                "failure_category": category,
                "error_message": _error_message(error),
                "failure_evidence": signals,
                "evidence_strength": "explicit",
                "source": "trace_event",
            })
        records.sort(key=_failure_sort_key)
        run_failure_signal = run_status == "failed"
        run_record = None
        if run_failure_signal and not records:
            run_record = {
                "event_id": None,
                "sequence_number": None,
                "event_type": "run_status",
                "event_name": "Run marked failed",
                "timestamp": None,
                "failure_category": "execution_failure",
                "error_message": None,
                "failure_evidence": ["run_status=failed; no failed trace event was available"],
                "evidence_strength": "explicit",
                "source": "run_status",
            }
        first = records[0] if records else run_record
        return {
            "failure_detected": bool(records or run_failure_signal),
            "first_detected_failure": first,
            "total_failure_events": len(records),
            "failure_records": records,
            "run_failure_signal": run_failure_signal,
            "run_status_only_failure": run_record,
        }


def _classify(event_type: Any, error: Any) -> str:
    classification = error.get("classification", error.get("category")) if isinstance(error, dict) else None
    classification = str(classification or "").lower()
    if event_type == "validation" or "validation" in classification:
        return "validation_failure"
    if classification in {"tool_error", "tool_failure"} or event_type in {"tool_call", "tool_result"} and _has_error(error):
        return "tool_failure"
    if classification in {"execution_error", "execution_failure"}:
        return "execution_failure"
    return "unknown_failure"


def _has_error(value: Any) -> bool:
    return value is not None and value is not False and value != "" and value != {}


def _error_message(value: Any) -> str | None:
    if isinstance(value, dict):
        message = value.get("message")
        return str(message) if message is not None else None
    return str(value) if value is not None else None


def _event_id(event: dict[str, Any]) -> str | None:
    value = event.get("event_id", event.get("id", event.get("_id")))
    return str(value) if value is not None else None


def _value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _failure_sort_key(record: dict[str, Any]) -> tuple[int, str, str]:
    sequence = record.get("sequence_number")
    timestamp = record.get("timestamp") or ""
    return (sequence if isinstance(sequence, int) and not isinstance(sequence, bool) else 2**63, timestamp, record.get("event_id") or "")


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value is not None else None)
