# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from datetime import datetime, timedelta
import json
import re
from genlayer import TreeMap, gl, u256

SERVICE = "https://api.carbonintensity.org.uk/intensity/"


def minute(text: str) -> datetime:
    if not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:(00|30)Z", text):
        raise gl.vm.UserError("Expected a UTC half-hour")
    try:
        return datetime.fromisoformat(text[:-1])
    except ValueError:
        raise gl.vm.UserError("Invalid UTC half-hour")


def stamp(value: datetime) -> str:
    return value.isoformat(timespec="minutes") + "Z"


def readings(rows: list, start: datetime, sections: int) -> list[int]:
    observed = []
    for index in range(sections):
        begin = start + timedelta(minutes=30 * index)
        end = begin + timedelta(minutes=30)
        matches = [
            row["intensity"]["actual"] for row in rows
            if row.get("from") == stamp(begin) and row.get("to") == stamp(end)
        ]
        if len(matches) != 1 or type(matches[0]) is not int or not 0 <= matches[0] <= 2000:
            raise gl.vm.UserError("Missing or invalid actual intensity")
        observed.append(matches[0])
    return observed


def next_mode(mode: str, actual: int, enter_at: int, exit_at: int) -> str:
    if actual <= enter_at:
        return "ALLOW"
    if actual >= exit_at:
        return "HOLD"
    return mode


class CarbonLatch(gl.Contract):
    cursor: str
    mode: str
    enter_at: u256
    exit_at: u256
    journal: TreeMap[str, str]

    def __init__(self, start: str, enter_at: u256, exit_at: u256):
        minute(start)
        if not 0 <= enter_at < exit_at <= 2000:
            raise gl.vm.UserError("Expected ordered thresholds")
        self.cursor = start
        self.enter_at = enter_at
        self.exit_at = exit_at
        self.mode = "HOLD"

    @gl.public.write
    def advance(self, expected: str, sections: int) -> str:
        if self.cursor != expected or not 1 <= sections <= 6:
            raise gl.vm.UserError("Stale cursor or invalid batch size")
        start = minute(expected)

        def observe() -> list[int]:
            end = start + timedelta(minutes=30 * sections)
            response = gl.nondet.web.get(SERVICE + expected + "/" + stamp(end))
            if response.status != 200 or not response.body or len(response.body) > 16384:
                raise gl.vm.UserError("Grid archive unavailable")
            return readings(json.loads(response.body)["data"], start, sections)

        observed = gl.eq_principle.strict_eq(observe)
        mode = self.mode
        for index, actual in enumerate(observed):
            key = stamp(start + timedelta(minutes=30 * index))
            mode = next_mode(mode, actual, self.enter_at, self.exit_at)
            self.journal[key] = json.dumps({"actual": actual, "mode": mode})
        self.mode = mode
        self.cursor = stamp(start + timedelta(minutes=30 * sections))
        return self.cursor

    @gl.public.view
    def checkpoint(self, start: str) -> str:
        return self.journal.get(start, "")

    @gl.public.view
    def state(self) -> str:
        return json.dumps({"cursor": self.cursor, "mode": self.mode})
