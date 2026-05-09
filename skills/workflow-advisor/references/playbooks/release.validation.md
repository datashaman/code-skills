# Release Validation

Handles `release.validation_window_closed`.

## Flow

1. Load release lifecycle state.
2. Check configured validation metrics and incidents during the window.
3. Evaluate `post_release_metrics_reviewed` and `validation_window_elapsed`.
4. Mark the release as validated, needs-follow-up, or rolled back.
5. Generate a concise report entry for process metrics.
