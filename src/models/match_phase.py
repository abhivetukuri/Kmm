"""Match phase detection based on scheduled times."""

from __future__ import annotations

from datetime import datetime, timezone

from kalshi_trader.util.time import current_epoch_ms


class MatchPhase(str):
    """Match phase."""

    PREMATCH = "PREMATCH"
    INPLAY = "INPLAY"
    STOP_QUOTING = "STOP_QUOTING"


def get_match_phase(
    start_time_utc: datetime,
    scheduled_end_time_utc: datetime,
    stop_before_end_seconds: int = 600,
) -> MatchPhase:
    """Get current match phase.

    Args:
        start_time_utc: Match start time (UTC)
        scheduled_end_time_utc: Scheduled end time (UTC)
        stop_before_end_seconds: Seconds before end to stop quoting

    Returns:
        Current match phase
    """
    now = datetime.now(timezone.utc)

    # Convert to UTC if naive
    if start_time_utc.tzinfo is None:
        start_time_utc = start_time_utc.replace(tzinfo=timezone.utc)
    if scheduled_end_time_utc.tzinfo is None:
        scheduled_end_time_utc = scheduled_end_time_utc.replace(tzinfo=timezone.utc)

    stop_quoting_time = scheduled_end_time_utc.timestamp() - stop_before_end_seconds

    if now.timestamp() < start_time_utc.timestamp():
        return MatchPhase.PREMATCH
    elif now.timestamp() >= stop_quoting_time:
        return MatchPhase.STOP_QUOTING
    else:
        return MatchPhase.INPLAY

