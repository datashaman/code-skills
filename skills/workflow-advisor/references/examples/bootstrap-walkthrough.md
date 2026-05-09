# Example: Bootstrap Walkthrough

This example shows the deterministic files produced by:

```bash
workflow-advisor interview --write-default --repo example/repo
```

## Files Created

```text
.workflow/
├── .gitignore
├── README.md
├── config.yml
├── schema_version
└── templates/
    ├── spec.md
    ├── pull_request_template.md
    ├── test-plan.md
    ├── obs-plan.md
    └── ...
```

## Starter Config Shape

```yaml
schema_version: 1
repo:
  provider: github
  identifier: example/repo
  default_branch: main
  branch_model: github-flow
profiles:
  spec-driven:
    enabled: true
  testability:
    enabled: true
  observability:
    enabled: true
transport:
  mode: on_demand_only
provider_actions:
  mode: queue
```

After bootstrap, run:

```bash
workflow-advisor doctor
workflow-advisor status
```

`doctor` may report informational empty-role findings until the team assigns
role members in `.workflow/config.yml`.
