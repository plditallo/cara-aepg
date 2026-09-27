from datetime import datetime, timezone


def parse_ts(value) -> datetime:
    """Parse an RFC 3339 timestamp into an aware UTC datetime.

    Raises ValueError on naive or malformed input. JSON Schema treats
    "format": "date-time" as an annotation only, so every timestamp that
    feeds an authorization decision is parsed here and a failure is
    treated as INDETERMINATE by the caller.
    """
    if isinstance(value, datetime):
        dt = value
    else:
        if not isinstance(value, str):
            raise ValueError(f"timestamp must be a string, got {type(value).__name__}")
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timestamp {value!r} has no UTC offset")
    return dt.astimezone(timezone.utc)
