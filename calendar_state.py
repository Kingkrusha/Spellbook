"""
Game calendars and clocks (Game Tools > Calendar). Pure logic, no UI.

A campaign has its own calendar: months of any length (a month can gain a day every N years), days that
sit outside the months (festival days: a "month" marked ``outside``, which by default doesn't move the
weekday on), a week of any number of named days, hours per day and minutes per hour. The current date and
time move forward (or back) with :meth:`Campaign.advance`, which also moves on the campaign's progress
trackers: a crafting project, a journey, a downtime activity. Each tracker can be set to advance by
itself or only when told to (when the work stopped).

Everything is saved in ``calendars.json`` in the user data folder (see :class:`CalendarStore`).
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

FILE_NAME = "calendars.json"
FORMAT_VERSION = 1


# --------------------------------------------------------------------------- #
# The calendar
# --------------------------------------------------------------------------- #

@dataclass
class Month:
    name: str
    days: int
    outside: bool = False              # days outside the months (festivals): shown on their own
    leap_every: int = 0                # gains a day in years divisible by this (0: never)
    counts_weekdays: Optional[bool] = None   # None: normal months count, "outside" days don't

    @property
    def moves_weekday(self) -> bool:
        return (not self.outside) if self.counts_weekdays is None else self.counts_weekdays

    def length(self, year: int) -> int:
        return self.days + (1 if self.leap_every and year % self.leap_every == 0 else 0)

    def to_dict(self) -> dict:
        d = {"name": self.name, "days": self.days}
        if self.outside:
            d["outside"] = True
        if self.leap_every:
            d["leap_every"] = self.leap_every
        if self.counts_weekdays is not None:
            d["counts_weekdays"] = self.counts_weekdays
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Month":
        return cls(str(d.get("name", "")), max(0, int(d.get("days", 30))), bool(d.get("outside", False)),
                   max(0, int(d.get("leap_every", 0) or 0)), d.get("counts_weekdays"))


@dataclass
class CalendarConfig:
    months: List[Month]
    weekdays: List[str]
    hours_per_day: int = 24
    minutes_per_hour: int = 60
    year_suffix: str = ""                 # shown after the year ("1492 DR")
    weekday_offset: int = 0               # shifts which weekday every date falls on

    # ---- lengths

    @property
    def minutes_per_day(self) -> int:
        return self.hours_per_day * self.minutes_per_hour

    def year_length(self, year: int) -> int:
        return sum(m.length(year) for m in self.months)

    def _days_before_year(self, year: int, weekday_only: bool = False) -> int:
        """Days from the start of year 0 to the start of ``year`` (negative before year 0)."""
        total = 0
        for m in self.months:
            if weekday_only and not m.moves_weekday:
                continue
            total += m.days * year
            if m.leap_every:
                total += (year + m.leap_every - 1) // m.leap_every   # leap years in [0, year)
        return total

    def day_of_year(self, year: int, month: int, day: int) -> int:
        """0-based day of the year."""
        return sum(self.months[i].length(year) for i in range(month)) + day - 1

    def to_ordinal(self, year: int, month: int, day: int) -> int:
        """Days since the start of year 0."""
        return self._days_before_year(year) + self.day_of_year(year, month, day)

    def from_ordinal(self, ordinal: int) -> Tuple[int, int, int]:
        """(year, month index, day) of a day count from :meth:`to_ordinal`."""
        mean = max(1, sum(m.days for m in self.months) + sum(1.0 / m.leap_every for m in self.months
                                                                if m.leap_every))
        year = int(ordinal // mean)
        while self._days_before_year(year) > ordinal:
            year -= 1
        while self._days_before_year(year + 1) <= ordinal:
            year += 1
        rest = ordinal - self._days_before_year(year)
        for i, m in enumerate(self.months):
            n = m.length(year)
            if rest < n:
                return year, i, rest + 1
            rest -= n
        return year, len(self.months) - 1, self.months[-1].length(year)   # (only with an empty calendar)

    def weekday(self, year: int, month: int, day: int) -> Optional[int]:
        """Index into ``weekdays`` (None on a day that doesn't count as a weekday, or with no weekdays)."""
        if not self.weekdays or not self.months[month].moves_weekday:
            return None
        n = self._days_before_year(year, weekday_only=True)
        n += sum(self.months[i].length(year) for i in range(month) if self.months[i].moves_weekday)
        n += day - 1 + self.weekday_offset
        return n % len(self.weekdays)

    # ---- text

    def year_text(self, year: int) -> str:
        return f"{year} {self.year_suffix}".strip()

    def date_text(self, year: int, month: int, day: int, weekday: bool = True) -> str:
        m = self.months[month]
        if m.outside and m.length(year) == 1:
            text = f"{m.name}, {self.year_text(year)}"
        else:
            text = f"{day} {m.name} {self.year_text(year)}"
        wd = self.weekday(year, month, day) if weekday else None
        return f"{self.weekdays[wd]}, {text}" if wd is not None else text

    def time_text(self, minute_of_day: int) -> str:
        h, m = divmod(minute_of_day, self.minutes_per_hour)
        width = max(2, len(str(self.minutes_per_hour - 1)))
        return f"{h:02d}:{m:0{width}d}"

    def to_dict(self) -> dict:
        return {"months": [m.to_dict() for m in self.months], "weekdays": list(self.weekdays),
                "hours_per_day": self.hours_per_day, "minutes_per_hour": self.minutes_per_hour,
                "year_suffix": self.year_suffix, "weekday_offset": self.weekday_offset}

    @classmethod
    def from_dict(cls, d: dict) -> "CalendarConfig":
        months = [Month.from_dict(m) for m in d.get("months", []) if isinstance(m, dict)]
        months = [m for m in months if m.days > 0 or m.leap_every] or [Month("Month", 30)]
        return cls(months, [str(w) for w in d.get("weekdays", [])],
                   max(1, int(d.get("hours_per_day", 24) or 24)), max(1, int(d.get("minutes_per_hour", 60) or 60)),
                   str(d.get("year_suffix", "") or ""), int(d.get("weekday_offset", 0) or 0))

    # ---- the months as editable text

    def months_text(self) -> str:
        lines = []
        for m in self.months:
            line = f"{m.name} {m.days}"
            if m.outside:
                line += " outside"
            if m.leap_every:
                line += f" leap {m.leap_every}"
            lines.append(line)
        return "\n".join(lines)


_MONTH_LINE = re.compile(r"^(?P<name>.*?)[\s,:|]+(?P<days>\d+)(?P<flags>(?:[\s,]+(?:outside|leap\s*\d+))*)\s*$",
                         re.IGNORECASE)


def parse_months(text: str) -> Tuple[List[Month], List[str]]:
    """Months from text, one per line: ``Name days [outside] [leap N]``. Returns (months, problems)."""
    months, problems = [], []
    for n, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        m = _MONTH_LINE.match(line)
        if not m or not m.group("name").strip():
            problems.append(f"Line {n}: write the name, then the number of days (\"{line}\").")
            continue
        flags = m.group("flags").lower()
        leap = re.search(r"leap\s*(\d+)", flags)
        days = int(m.group("days"))
        if days <= 0 and not leap:
            problems.append(f"Line {n}: a month needs at least one day.")
            continue
        months.append(Month(m.group("name").strip(), days, "outside" in flags,
                            int(leap.group(1)) if leap else 0))
    if not months:
        problems.append("Add at least one month.")
    return months, problems


# --------------------------------------------------------------------------- #
# Presets (plain, setting-neutral calendars to start from)
# --------------------------------------------------------------------------- #

def preset(name: str) -> CalendarConfig:
    if name == "Gregorian":
        lengths = [("January", 31), ("February", 28), ("March", 31), ("April", 30), ("May", 31), ("June", 30),
                   ("July", 31), ("August", 31), ("September", 30), ("October", 31), ("November", 30),
                   ("December", 31)]
        months = [Month(n, d, leap_every=4 if n == "February" else 0) for n, d in lengths]
        # (a leap day every 4 years matches the real calendar from 1901 to 2099; the offset lines the
        # weekdays up with it there)
        return CalendarConfig(months, ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
                                       "Sunday"], weekday_offset=4)
    if name == "Twelve thirties with festivals":
        months = []
        for i in range(12):
            months.append(Month(f"Month {i + 1}", 30))
            if i % 3 == 2:
                months.append(Month(f"Festival {i // 3 + 1}", 1, outside=True))
        months.append(Month("Leap Festival", 0, outside=True, leap_every=4))
        return CalendarConfig(months, [f"Day {i + 1}" for i in range(10)])
    # "Simple": twelve months of thirty days, seven-day weeks
    return CalendarConfig([Month(f"Month {i + 1}", 30) for i in range(12)],
                          ["First-day", "Second-day", "Third-day", "Fourth-day", "Fifth-day", "Sixth-day",
                           "Seventh-day"])


PRESETS = ["Simple", "Gregorian", "Twelve thirties with festivals"]


# --------------------------------------------------------------------------- #
# Events and trackers
# --------------------------------------------------------------------------- #

@dataclass
class Event:
    """A holiday (every year) or a one-off event on a date."""
    name: str
    month: int
    day: int
    year: Optional[int] = None         # None: every year (a holiday)
    description: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def is_holiday(self) -> bool:
        return self.year is None

    def on(self, year: int, month: int, day: int) -> bool:
        return self.month == month and self.day == day and (self.year is None or self.year == year)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "month": self.month, "day": self.day, "year": self.year,
                "description": self.description}

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(str(d.get("name", "")), int(d.get("month", 0)), int(d.get("day", 1)),
                   None if d.get("year") is None else int(d["year"]), str(d.get("description", "") or ""),
                   str(d.get("id") or uuid.uuid4().hex[:12]))


UNITS = ("hours", "days")


@dataclass
class Tracker:
    """Something that takes a while: progress (in hours or days of game time) toward a total."""
    name: str
    total: float
    unit: str = "days"                 # "hours" or "days"
    progress: float = 0.0
    auto: bool = True                  # moves on when the clock does
    notes: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def done(self) -> bool:
        return self.total > 0 and self.progress >= self.total - 1e-9

    @property
    def fraction(self) -> float:
        return 0.0 if self.total <= 0 else max(0.0, min(1.0, self.progress / self.total))

    def add(self, amount: float) -> bool:
        """Move on by ``amount`` units (back when negative). True if this finished it."""
        was_done = self.done
        self.progress = max(0.0, min(self.total, self.progress + amount))
        return self.done and not was_done

    def progress_text(self) -> str:
        def num(x):
            return f"{x:.1f}".rstrip("0").rstrip(".")
        unit = self.unit if self.total != 1 else self.unit[:-1]
        return f"{num(self.progress)} of {num(self.total)} {unit}" + (" (done)" if self.done else "")

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "total": self.total, "unit": self.unit,
                "progress": self.progress, "auto": self.auto, "notes": self.notes}

    @classmethod
    def from_dict(cls, d: dict) -> "Tracker":
        unit = d.get("unit") if d.get("unit") in UNITS else "days"
        return cls(str(d.get("name", "")), max(0.0, float(d.get("total", 1) or 0)), unit,
                   max(0.0, float(d.get("progress", 0) or 0)), bool(d.get("auto", True)),
                   str(d.get("notes", "") or ""), str(d.get("id") or uuid.uuid4().hex[:12]))


@dataclass
class AdvanceReport:
    finished: List[Tracker] = field(default_factory=list)
    events: List[Tuple[Tuple[int, int, int], Event]] = field(default_factory=list)   # passed or reached

    def messages(self, config: CalendarConfig, limit: int = 8) -> List[str]:
        out = [f"Finished: {t.name}" for t in self.finished]
        for (y, m, d), e in self.events[:limit]:
            out.append(f"{e.name} ({config.date_text(y, m, d, weekday=False)})")
        if len(self.events) > limit:
            out.append(f"and {len(self.events) - limit} more events")
        return out


# --------------------------------------------------------------------------- #
# A campaign: one calendar, its date and time, events and trackers
# --------------------------------------------------------------------------- #

@dataclass
class Campaign:
    name: str
    config: CalendarConfig
    year: int = 1
    month: int = 0
    day: int = 1
    minute: int = 8 * 60                # minute of the day
    events: List[Event] = field(default_factory=list)
    trackers: List[Tracker] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def __post_init__(self):
        self.clamp()

    def clamp(self):
        """Keep the date and time valid (after the calendar was edited)."""
        c = self.config
        self.month = max(0, min(self.month, len(c.months) - 1))
        length = c.months[self.month].length(self.year)
        if length <= 0:                           # a leap-only month in a normal year: the next real day
            self.year, self.month, self.day = c.from_ordinal(c.to_ordinal(self.year, self.month, 1))
        else:
            self.day = max(1, min(self.day, length))
        self.minute = max(0, min(self.minute, c.minutes_per_day - 1))

    # ---- reading

    @property
    def ordinal(self) -> int:
        return self.config.to_ordinal(self.year, self.month, self.day)

    @property
    def total_minutes(self) -> int:
        return self.ordinal * self.config.minutes_per_day + self.minute

    def date_text(self) -> str:
        return self.config.date_text(self.year, self.month, self.day)

    def time_text(self) -> str:
        return self.config.time_text(self.minute)

    def events_on(self, year: int, month: int, day: int) -> List[Event]:
        return [e for e in self.events if e.on(year, month, day)]

    # ---- moving the clock

    def set_datetime(self, year: int, month: int, day: int, minute: Optional[int] = None,
                     move_trackers: bool = False) -> AdvanceReport:
        """Jump to a date (and time). With ``move_trackers`` the jump counts as time passing."""
        c = self.config
        month = max(0, min(month, len(c.months) - 1))
        day = max(1, min(day, max(1, c.months[month].length(year))))
        minute = self.minute if minute is None else max(0, min(minute, c.minutes_per_day - 1))
        target = c.to_ordinal(year, month, day) * c.minutes_per_day + minute
        if move_trackers:
            return self.advance(target - self.total_minutes)
        self.year, self.month, self.day, self.minute = year, month, day, minute
        self.clamp()
        return AdvanceReport()

    def advance(self, minutes: int) -> AdvanceReport:
        """Move the clock on by ``minutes`` (back when negative), and the automatic trackers with it."""
        report = AdvanceReport()
        if not minutes:
            return report
        c = self.config
        start_day = self.ordinal
        total = self.total_minutes + minutes
        day_ord, self.minute = divmod(total, c.minutes_per_day)
        self.year, self.month, self.day = c.from_ordinal(day_ord)

        hours = minutes / c.minutes_per_hour
        for t in self.trackers:
            if not t.auto:
                continue
            amount = hours if t.unit == "hours" else hours / c.hours_per_day
            if t.add(amount):
                report.finished.append(t)

        if minutes > 0 and day_ord > start_day and self.events:
            # the events of each day the clock moved into (capped: a jump of centuries lists only the first)
            for o in range(start_day + 1, min(day_ord, start_day + 3660) + 1):
                ymd = c.from_ordinal(o)
                for e in self.events_on(*ymd):
                    report.events.append((ymd, e))
        return report

    def advance_days(self, days: int) -> AdvanceReport:
        return self.advance(days * self.config.minutes_per_day)

    # ---- files

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "config": self.config.to_dict(), "year": self.year,
                "month": self.month, "day": self.day, "minute": self.minute,
                "events": [e.to_dict() for e in self.events], "trackers": [t.to_dict() for t in self.trackers]}

    @classmethod
    def from_dict(cls, d: dict) -> "Campaign":
        return cls(str(d.get("name", "") or "Campaign"), CalendarConfig.from_dict(d.get("config") or {}),
                   int(d.get("year", 1)), int(d.get("month", 0)), int(d.get("day", 1)),
                   int(d.get("minute", 8 * 60)),
                   [Event.from_dict(e) for e in d.get("events", []) if isinstance(e, dict)],
                   [Tracker.from_dict(t) for t in d.get("trackers", []) if isinstance(t, dict)],
                   str(d.get("id") or uuid.uuid4().hex[:12]))


def new_campaign(name: str, preset_name: str = "Simple", year: int = 1) -> Campaign:
    return Campaign(name, preset(preset_name), year=year)


# --------------------------------------------------------------------------- #
# Saving
# --------------------------------------------------------------------------- #

class CalendarStore:
    """Every campaign's calendar, in one JSON file."""

    def __init__(self, path: Optional[str] = None):
        if path is None:
            from paths import user_data_path
            path = user_data_path(FILE_NAME)
        self.path = path
        self.campaigns: List[Campaign] = []
        self.active_id: Optional[str] = None
        self.load()

    def load(self):
        self.campaigns, self.active_id = [], None
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            print(f"Could not read {self.path}: {e}")
            return
        for d in data.get("campaigns", []) if isinstance(data, dict) else []:
            try:
                self.campaigns.append(Campaign.from_dict(d))
            except (TypeError, ValueError) as e:
                print(f"Skipped a calendar that could not be read: {e}")
        self.active_id = data.get("active") if isinstance(data, dict) else None

    def save(self) -> bool:
        from atomic_io import atomic_write_json
        try:
            atomic_write_json(self.path, {"version": FORMAT_VERSION, "active": self.active_id,
                                          "campaigns": [c.to_dict() for c in self.campaigns]})
            return True
        except OSError as e:
            print(f"Could not save the calendars: {e}")
            return False

    @property
    def active(self) -> Optional[Campaign]:
        for c in self.campaigns:
            if c.id == self.active_id:
                return c
        return self.campaigns[0] if self.campaigns else None

    def get(self, campaign_id: str) -> Optional[Campaign]:
        return next((c for c in self.campaigns if c.id == campaign_id), None)

    def add(self, campaign: Campaign) -> Campaign:
        self.campaigns.append(campaign)
        self.active_id = campaign.id
        self.save()
        return campaign

    def remove(self, campaign_id: str):
        self.campaigns = [c for c in self.campaigns if c.id != campaign_id]
        if self.active_id == campaign_id:
            self.active_id = self.campaigns[0].id if self.campaigns else None
        self.save()


_store: Optional[CalendarStore] = None


def get_calendar_store() -> CalendarStore:
    global _store
    if _store is None:
        _store = CalendarStore()
    return _store
