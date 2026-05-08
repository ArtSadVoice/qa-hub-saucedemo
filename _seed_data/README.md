# `_seed_data/` — Pre-populated demo state

Drop these files into `hub/` (and `hub/bugs/`) to make a fresh hub install
look "lived-in" — 2 weeks of run history, 4 sample bugs, 1 daily schedule.
The setup script does this automatically; you can also do it by hand:

```bash
cp _seed_data/run_history.json    hub/run_history.json
cp _seed_data/schedules.json      hub/schedules.json
mkdir -p                          hub/bugs
cp _seed_data/bugs/saucedemo-e2e.json  hub/bugs/saucedemo-e2e.json
```

Why seed?
- A blank dashboard (no runs, no bugs, no trend) looks empty and confusing
- Recruiters / interviewers want to see what the dashboard looks like
  *while in use*, not on day zero
- The 17 passing tests + 4 bugs + trend chart show off the hub's full
  feature surface in 30 seconds

## What's inside

| File | Content |
|------|---------|
| `run_history.json` | 17 run entries spanning 2026-04-25 → 2026-05-08, mostly green with intentional friday-deploy dips |
| `schedules.json` | One daily smoke schedule at 02:00 |
| `bugs/saucedemo-e2e.json` | 4 bugs (Medium/Low/Low/High; Open/Open/Fixed/Closed) |

All entries reference real test cases (`TS_01_01`, `TS_06_01`, etc.) so
the dashboard's TCID linking works.
