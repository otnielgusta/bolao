import datetime as dt
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from fastapi.templating import Jinja2Templates


try:
    APP_TIMEZONE = ZoneInfo("America/Sao_Paulo")
except ZoneInfoNotFoundError:
    APP_TIMEZONE = dt.timezone(dt.timedelta(hours=-3), "BRT")


def local_datetime(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(APP_TIMEZONE)


def local_strftime(value: dt.datetime | None, fmt: str) -> str:
    local_value = local_datetime(value)
    if local_value is None:
        return ""
    return local_value.strftime(fmt)


def create_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory="app/templates")
    templates.env.filters["local_datetime"] = local_datetime
    templates.env.filters["local_strftime"] = local_strftime
    return templates
