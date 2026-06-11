import datetime as dt

from app.templating import local_strftime


def test_local_strftime_converts_utc_to_brasilia_time():
    kickoff = dt.datetime(2026, 6, 12, 2, 0, tzinfo=dt.timezone.utc)

    assert local_strftime(kickoff, "%d/%m/%Y %H:%M") == "11/06/2026 23:00"


def test_local_strftime_treats_naive_datetimes_as_utc():
    kickoff = dt.datetime(2026, 6, 12, 2, 0)

    assert local_strftime(kickoff, "%d/%m %H:%M") == "11/06 23:00"
