# Reconfigure

Use this reference when `.workflow/config.yml` changes or the user asks to
change enabled profiles, roles, gates, labels, transports, or reporting policy.

Reconfiguration is not a direct write path. Treat the proposed config change as
an input to the reconcile loop:

1. Load the current config and the proposed config.
2. Compute a structural diff with `helpers/config_io.py`.
3. Classify the changed sections:
   - `profiles`: recompose lifecycle and regenerate affected templates.
   - `roles`: re-evaluate open gates that reference changed roles.
   - `labels`: compute taxonomy drift and propose provider label updates.
   - `transport`: regenerate provider wiring, but do not apply branch
     protection automatically.
   - `lifecycle.gates`: re-evaluate open lifecycle items.
4. Produce a dry-run summary first.
5. On confirmation, write `.workflow/config.yml`, derived lifecycle files, and
   any proposed `.github/` files through checkpointed reconcile.

## Safety

- Branch protection remains suggest-only.
- Provider changes are proposed unless the config explicitly allows them.
- Open items are re-evaluated; historical gate decisions are not rewritten.
- Empty required roles route to `tech_lead` with a role-assignment warning.

The operational slash commands that trigger this flow are documented in
`playbooks/operational.md`.
