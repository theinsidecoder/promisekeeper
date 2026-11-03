# 🤝 PromiseKeeper

> **"I'll send it by Friday."** — Everyone says it. Nobody tracks it.
> PromiseKeeper reads your chats & emails and builds the to-do list you forgot to write.

![python](https://img.shields.io/badge/python-3.9%2B-blue) ![deps](https://img.shields.io/badge/dependencies-0-brightgreen) ![offline](https://img.shields.io/badge/privacy-100%25%20offline-purple) ![tests](https://img.shields.io/badge/tests-11%20passing-success)

## The problem
Every day, real commitments get buried in WhatsApp threads, emails, and meeting notes:
*"I'll call the landlord tomorrow"*, *"can you sign this by Friday?"*, *"remind me to pay rent on the 1st."*
Missed promises cost friendships, money, and jobs, and nobody wants to copy-paste them into a task app.

## The solution
Paste any conversation. PromiseKeeper finds the commitments, works out **who owes what**, parses the **deadline**
(even "next Tuesday at 5pm", "in 2 weeks", "before the 20th"), ranks urgency, and exports a **calendar file** with reminders.

```
$ python promisekeeper.py --demo

YOU OWE (3)
 🔴 2026-11-04 09:00 I'll start tomorrow at 9am
 🟡 2026-11-06       Can you review the contract by Friday?
 🟢 2026-11-20       I need to renew my passport before the 20th

OWED TO YOU (3)
 🔴 2026-11-03       Please don't forget to call the landlord today  (Sam)
 🟡 2026-11-10       I'll book the venue next Tuesday and let you know ASAP  (Sam)
 🟢 2026-12-01       Remind me to pay rent on the 1st of December  (Sam)
```

## Why it's different
| | PromiseKeeper | Typical AI to-do apps |
|---|---|---|
| Privacy | **100% offline**, nothing leaves your machine | Uploads your private chats |
| Cost | Free, **zero dependencies** | API keys & subscriptions |
| Direction-aware | Separates **"you owe"** vs **"owed to you"** | Flat task list |
| Output | `.ics` calendar, JSON, terminal | Locked in their app |
| Speed | Milliseconds | Network round-trips |

## Quick start
```bash
git clone https://github.com/<you>/promisekeeper && cd promisekeeper
python promisekeeper.py --demo                                  # try it
python promisekeeper.py chat.txt --me Sam --ics promises.ics    # real chat -> calendar
cat email.txt | python promisekeeper.py --json                  # pipe anything
python -m unittest -v                                           # run the tests
```
Supports plain text, `Name: message` chats, and WhatsApp exports (`12/03/2026, 10:15 - Sam: ...`).
Import the `.ics` into Google Calendar, Apple Calendar, or Outlook.

## How it works
1. **Segment**: split into speakers and sentences.
2. **Detect intent**: commitment patterns (*I'll, let me, I need to*) vs request patterns (*can you, please, don't forget*).
3. **Assign ownership**: commitments bind the speaker; requests bind the other person; `--me` decides the direction.
4. **Parse time**: a rule-based temporal parser handles relative dates, weekdays (`next` vs `this`), calendar dates with year roll-over, clock times, and phrases like *EOD* and *end of month*.
5. **Prioritise**: due within 24h or urgent words (*ASAP*) → 🔴, within 3 days → 🟡, else 🟢.
6. **Export**: table, JSON, or `.ics` with a 1-hour-before alarm.

Deterministic, explainable, testable. Every decision traces back to a readable rule.

## Project layout
```
promisekeeper.py        # parser, extractor, CLI, ICS exporter (~200 lines)
test_promisekeeper.py   # 11 unit tests covering dates, ownership, exports
```

## Roadmap
- [ ] Optional LLM mode for ambiguous phrasing
- [ ] Multi-language date parsing
- [ ] `watch` mode for live chat exports

## License
MIT. PRs welcome.
