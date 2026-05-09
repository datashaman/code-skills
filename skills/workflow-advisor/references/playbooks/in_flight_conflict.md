# In-Flight Conflict

Handles `lifecycle.in_flight_conflict_detected`.

## Flow

1. Preserve the active item in its current stage.
2. Add a `blocked:in-flight-conflict` target label.
3. Notify the responsible role with the source change and the action that would
   have happened without protection.
4. Offer explicit choices: rebase/update, split follow-up, override, or close.
5. Log the chosen path.

This playbook exists to avoid silent rewinds of work already in review or close
to merge.
