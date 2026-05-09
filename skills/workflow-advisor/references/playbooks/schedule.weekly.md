# Weekly Schedule

Handles `schedule.weekly`.

## Flow

1. Run daily schedule checks.
2. Generate process, cycle-time, and gate-friction rollups.
3. Apply retention rules for archived sidecars and raw event logs.
4. Summarize role load and repeated blockers.
5. Commit aggregated reports if configured.
