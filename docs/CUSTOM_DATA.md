# Bring your own data — train and calibrate FUT-K on YOUR datasets

FUT-K's engine is a pure function of a normalized event stream. It does not
care whether the stream came from StatsBomb, your club's scouts, a scraper,
or a spreadsheet you typed by hand. This page is the complete walkthrough:
put your data in the open format below, ingest it, replay it in the app, and
**recalibrate the model on it** — protected by the same promotion gate as
every official dataset.

## 1. The interchange format

One row per event, CSV (with header) or JSON (list of objects). Seven
required fields, three optional:

| Field | Required | Meaning |
|---|---|---|
| `match_id` | yes | your identifier — one per match, any string |
| `date` | yes | ISO `yyyy-mm-dd` |
| `home_team` / `away_team` | yes | names (used for display and Explore) |
| `minute` | yes | 0–150, decimals welcome (`63.4`) |
| `team` | yes | `HOME` or `AWAY` |
| `type` | yes | one of `goal`, `shot`, `shot_on_target`, `corner`, `foul`, `yellow_card`, `red_card` |
| `x`, `y` | no | pitch location, 0–100 in the acting team's attacking frame (enables the 2D replay) |
| `player_id` | no | any stable id (enables Player DNA click-through) |

Ground rules, honestly enforced:

- **Bad rows are reported, never silently dropped.** The ingester prints every
  rejected row with its reason.
- **The final score is derived from your goal events** — one source of truth,
  no separate score column to disagree with itself.
- Every match gets an `events_hash` provenance digest, so any experiment can
  state exactly which data produced it.

A ready-to-run sample ships in
[`examples/custom_events_sample.csv`](../examples/custom_events_sample.csv)
(10 small fictional matches).

## 2. Ingest

```bash
cd backend
export DATABASE_URL=...        # or omit for local SQLite

python scripts/ingest_custom.py --file ../examples/custom_events_sample.csv \
    --competition my-league
```

`--competition` is your label; it scopes everything downstream. Re-running is
idempotent (existing `match_id`s are skipped; `--replace` overwrites).

Your matches now behave like any other: they appear in `GET /matches?competition=my-league`,
replay minute by minute in the app (2D pitch included if you provided `x`/`y`),
answer questions, and join Explore queries.

## 3. Calibrate the model on your data

```bash
python scripts/recalibrate.py --from-db --competition my-league
```

What happens — the same learning loop that governs official data
(validation §5.8):

1. Your matches are ordered by date; the model refits `base_rate`/`tau` on
   the **older 75%**.
2. The new fit AND the currently active parameters are both scored on the
   **most recent 25%** (held-out, never trained on).
3. The new version is **promoted only if held-out log loss does not degrade**
   — otherwise it is recorded as rejected and nothing changes.
4. Every attempt lands in `GET /model/versions`, promoted or not.

You need at least 8 matches for an honest refit (the script refuses fewer).
The gate means you cannot hurt yourself: if your dataset is too small, too
noisy, or simply agrees with the current parameters, the refit is rejected
with the numbers that say why.

## 4. What FUT-K promises about your data

- **Determinism** — same file, same result, today and in six months. No LLMs,
  no randomness anywhere in ingestion or calibration.
- **Honesty** — rejected rows, rejected refits, and provenance hashes are all
  first-class outputs, not hidden logs.
- **Locality** — your data stays in your database. Nothing is uploaded
  anywhere.

## Tips for good calibration data

- More matches beat more event types: 40 matches of goals-only calibrate the
  goal model better than 10 matches of everything.
- Decimal minutes help the temporal model (`63.4`, not just `63`).
- If you can, include shots: pressure features feed the in-play reading.
- Mixed sources? Run each through the Data Fusion Layer's interchange first —
  or just label them as different competitions and calibrate per source.
