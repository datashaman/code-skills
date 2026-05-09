# Artifact State Changed

Handles `artifact.state_changed`.

## Flow

1. Load the artifact sidecar.
2. Validate the requested transition against the active profile rules.
3. Re-evaluate dependent lifecycle items.
4. Compute cascade effects if the state change invalidates downstream work.
5. Log the decision and metrics.

State changes must pass through reconcile so sidecars, comments, and metrics stay
consistent.
