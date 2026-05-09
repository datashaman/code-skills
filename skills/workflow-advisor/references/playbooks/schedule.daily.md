# Daily Schedule

Handles `schedule.daily`.

## Flow

1. Run a full observe pass.
2. Detect artifact drift and stale lifecycle items.
3. Re-evaluate open gates with time-sensitive inputs.
4. Poll review-thread status if configured.
5. Queue status updates only for changed state.
6. Append metrics events.
