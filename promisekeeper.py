#!/usr/bin/env python3
"""PromiseKeeper - turn messy chats & emails into a deadline-sorted promise list.

Zero dependencies. 100% offline. Your messages never leave your machine.

    python promisekeeper.py chat.txt --me Sam --ics promises.ics
    cat email.txt | python promisekeeper.py --json
    python promisekeeper.py --demo
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_MON = "|".join(m for m in MONTHS)
_DAY = "|".join(DAYS)

# ---- what counts as a promise ------------------------------------------------
COMMIT = re.compile(
    r"\b(i['’]ll|i will|i['’]m going to|i am going to|i can|i promise|let me|we['’]ll|we will|"
    r"i['’]ll make sure|i need to|i have to|i must|i should|remind me to|todo)\b", re.I)
REQUEST = re.compile(
    r"\b(can you|could you|would you|will you|please|don['’]t forget|remember to|"
    r"need you to|make sure you)\b", re.I)
URGENT = re.compile(r"\b(urgent|asap|important|critical|immediately|deadline)\b", re.I)
SPEAKER = re.compile(
    r"^(?:\[?\d{1,2}[/.]\d{1,2}[/.]\d{2,4},?\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?\]?\s*[-–]?\s*)?"
    r"([A-Za-z][^:\n]{0,29}):\s+(.+)$")


# ---- date parsing ------------------------------------------------------------
def _end_of(d: date, h: int = 17) -> datetime:
    return datetime.combine(d, time(h))


def _weekday_date(today: date, wd: int, nxt: bool) -> date:
    ahead = (wd - today.weekday()) % 7 or 7
    target = today + timedelta(days=ahead)
    if nxt and target.isocalendar()[:2] == today.isocalendar()[:2]:
        target += timedelta(days=7)
    return target


def _clock(text: str) -> time | None:
    m = re.search(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text, re.I) or \
        re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?()\b", text, re.I)
    if m:
        h, mi, ap = int(m[1]), int(m[2] or 0), m[3].lower()
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        if h < 24 and mi < 60:
            return time(h, mi)
    for word, t in (("noon", time(12)), ("midnight", time(23, 59)), ("morning", time(9)),
                    ("afternoon", time(15)), ("evening", time(18)), ("tonight", time(20)),
                    ("eod", time(17)), ("end of day", time(17)), ("end of the day", time(17))):
        if re.search(rf"\b{word}\b", text, re.I):
            return t
    return None


def parse_due(text: str, today: date) -> datetime | date | None:
    """Return a datetime (date + time) or a plain date. None if no deadline found."""
    t = text.lower()
    clock = _clock(t)
    found: date | None = None

    if m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t):
        found = date(int(m[1]), int(m[2]), int(m[3]))
    elif m := re.search(r"\bin (\d+|a|an|one|two|three) (hour|day|week|month)s?\b", t):
        n = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3}.get(m[1]) or int(m[1])
        if m[2] == "hour":
            return datetime.now().replace(second=0, microsecond=0) + timedelta(hours=n)
        found = today + timedelta(days={"day": 1, "week": 7, "month": 30}[m[2]] * n)
    elif m := re.search(rf"\b({_MON})[a-z]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", t) or \
            re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MON})[a-z]*\b", t):
        a, b = m[1], m[2]
        mon, day = (a, b) if a.isalpha() else (b, a)
        try:
            found = date(today.year, MONTHS.index(mon[:3]) + 1, int(day))
            if found < today:
                found = found.replace(year=today.year + 1)
        except ValueError:
            found = None
    elif m := re.search(rf"\b(next|this|on|by|before)?\s*({_DAY})\b", t):
        found = _weekday_date(today, DAYS.index(m[2]), m[1] == "next")
    elif "day after tomorrow" in t:
        found = today + timedelta(days=2)
    elif "tomorrow" in t:
        found = today + timedelta(days=1)
    elif re.search(r"\b(today|tonight|eod|end of (the )?day)\b", t):
        found = today
    elif "next week" in t:
        found = today + timedelta(days=7 - today.weekday())
    elif re.search(r"\b(this weekend)\b", t):
        found = _weekday_date(today, 5, False)
    elif re.search(r"\bend of (the )?week\b", t):
        found = _weekday_date(today, 4, False) if today.weekday() < 4 else today
    elif re.search(r"\bend of (the )?month\b", t):
        nxt = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        found = nxt - timedelta(days=1)
    elif m := re.search(r"\b(?:by|on|before) the (\d{1,2})(?:st|nd|rd|th)\b", t):
        try:
            found = today.replace(day=int(m[1]))
            if found < today:
                found = (today.replace(day=28) + timedelta(days=4)).replace(day=int(m[1]))
        except ValueError:
            found = None

    if found is None:
        return None
    return datetime.combine(found, clock) if clock else found


# ---- extraction ---------------------------------------------------------------
@dataclass
class Promise:
    task: str
    direction: str          # "i_owe" | "owed_to_me"
    who: str                # person responsible
    due: str | None         # ISO string
    priority: str           # HIGH | MED | LOW
    source: str

    @property
    def due_dt(self) -> datetime | None:
        if not self.due:
            return None
        return datetime.fromisoformat(self.due)


def _priority(due: datetime | date | None, text: str, today: date) -> str:
    days = 99
    if due is not None:
        d = due.date() if isinstance(due, datetime) else due
        days = (d - today).days
    score = 2 if days <= 1 else 1 if days <= 3 else 0
    score += 1 if URGENT.search(text) else 0
    return "HIGH" if score >= 2 else "MED" if score == 1 else "LOW"


def _clean(sentence: str) -> str:
    s = re.sub(r"^(ok(ay)?|sure|yes|yeah|hey|hi|thanks|cool|alright|also|great)[,.!\s]+", "", sentence.strip(), flags=re.I)
    s = s.strip(" .!;,-")
    return s[:1].upper() + s[1:]


def extract(text: str, me: str = "me", today: date | None = None) -> list[Promise]:
    today = today or date.today()
    out: list[Promise] = []
    seen: set[str] = set()
    other = "them"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        speaker = None
        if m := SPEAKER.match(line):
            speaker, line = m[1].strip(), m[2]
        is_me = speaker is None or speaker.lower() == me.lower()
        if not is_me:
            other = speaker
        for sent in re.split(r"(?<=[.!?])\s+", line):
            commit, request = COMMIT.search(sent), REQUEST.search(sent)
            if not (commit or request):
                continue
            # A request asks the *other* person; a commitment binds the speaker.
            if commit and not (request and request.start() < commit.start()):
                mine, who = is_me, (me if is_me else speaker)
            else:
                mine, who = (not is_me) or speaker is None, (me if (not is_me or speaker is None) else other)
            if speaker is None and request and not commit:
                mine, who = True, me
            due = parse_due(sent, today)
            key = re.sub(r"\W+", " ", sent.lower()).strip()
            if key in seen:
                continue
            seen.add(key)
            out.append(Promise(_clean(sent), "i_owe" if mine else "owed_to_me", who,
                               due.isoformat() if due else None, _priority(due, sent, today), raw.strip()))
    out.sort(key=lambda p: (p.due is None, p.due or "", p.priority))
    return out


# ---- output --------------------------------------------------------------------
def to_ics(promises: list[Promise]) -> str:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PromiseKeeper//EN"]
    for p in promises:
        if not p.due:
            continue
        d = p.due_dt
        lines += ["BEGIN:VEVENT", f"UID:{uuid.uuid4()}@promisekeeper", f"DTSTAMP:{stamp}",
                  f"SUMMARY:{'[Owed] ' if p.direction == 'owed_to_me' else ''}{p.task}".replace(",", "\\,")]
        if "T" in p.due:
            lines += [f"DTSTART:{d:%Y%m%dT%H%M%S}", f"DTEND:{d + timedelta(minutes=30):%Y%m%dT%H%M%S}"]
        else:
            lines += [f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}"]
        lines += ["BEGIN:VALARM", "TRIGGER:-PT1H", "ACTION:DISPLAY", "DESCRIPTION:Promise due", "END:VALARM",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def render(promises: list[Promise]) -> str:
    if not promises:
        return "No promises found. Either you are free, or nobody committed to anything."
    icon = {"HIGH": "🔴", "MED": "🟡", "LOW": "🟢"}
    sections = []
    for title, key in (("YOU OWE", "i_owe"), ("OWED TO YOU", "owed_to_me")):
        rows = [p for p in promises if p.direction == key]
        if rows:
            body = "\n".join(
                f" {icon[p.priority]} {(p.due or 'no date').replace('T', ' ')[:16]:<16} {p.task}"
                + ("" if key == "i_owe" else f"  ({p.who})") for p in rows)
            sections.append(f"{title} ({len(rows)})\n{body}")
    return "\n\n".join(sections)


DEMO = """Sam: Can you review the contract by Friday?
Alex: Sure, I'll start tomorrow at 9am. Also I need to renew my passport before the 20th.
Sam: Great. I'll book the venue next Tuesday and let you know ASAP.
Alex: Please don't forget to call the landlord today.
Sam: Remind me to pay rent on the 1st of December!
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract promises & deadlines from chats/emails. Offline.")
    ap.add_argument("file", nargs="?", help="text file (default: stdin)")
    ap.add_argument("--me", default="me", help="your name as it appears in the chat (default: me)")
    ap.add_argument("--ics", metavar="PATH", help="write a calendar file you can import anywhere")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD)")
    ap.add_argument("--demo", action="store_true", help="run on a built-in example (--me Alex)")
    a = ap.parse_args(argv)

    today = date.fromisoformat(a.today) if a.today else date.today()
    if a.demo:
        text, a.me = DEMO, "Alex"
    elif a.file:
        text = open(a.file, encoding="utf-8").read()
    else:
        text = sys.stdin.read()

    found = extract(text, a.me, today)
    print(json.dumps([asdict(p) for p in found], indent=2, ensure_ascii=False) if a.json else render(found))
    if a.ics:
        with open(a.ics, "w", encoding="utf-8", newline="") as f:
            f.write(to_ics(found))
        print(f"\n📅 Wrote {sum(1 for p in found if p.due)} events to {a.ics}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
