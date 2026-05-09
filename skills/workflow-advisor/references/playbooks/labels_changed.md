# Labels Changed

Handles PR and issue label changes.

## Flow

1. Normalize aliases to canonical labels.
2. Enforce mutual-exclusion groups in the sidecar target state.
3. Detect externally applied workflow labels and log them as manual overrides.
4. Re-run type, area, and blocker classification when relevant.
5. Queue provider label diffs only when the configured authority allows it.

This playbook keeps provider labels and `.workflow/` sidecars aligned without
making labels the sole source of truth.
