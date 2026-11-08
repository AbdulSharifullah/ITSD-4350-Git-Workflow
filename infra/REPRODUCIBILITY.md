# Mini Project 2.2 — execution record

Status: implementation in progress; lifecycle execution is not yet verified.

## Verified baseline — November 8, 2026

- Existing repository inspected and fetched; `main` matched `origin/main` at
  `24097b1` before creating `feature/staging-terraform-iac`.
- Existing unrelated uncommitted coursework was preserved.
- Windows baseline regression: 13 pytest tests passed, 98% aggregate coverage.
- Existing Flake8 command passed with exit code 0.
- Protected `main` requires `build-and-test`, `SonarCloud Code Analysis`, and one
  approving review; administrator enforcement is enabled.
- No AWS resources were created and no local infrastructure tools were installed.

## Lifecycle procedure and expected evidence

The manually dispatched `Terraform Staging` workflow runs these actual commands
through `infra/demonstrate.sh`:

1. Save a plan, apply it, and record image/container/network outputs.
2. Run the repository's existing HTTPS smoke test and save health/form responses.
3. Verify loopback-only publishing, internal networking, blocked direct egress,
   and recovery after a container restart.
4. Require a no-drift plan (exit code 0).
5. Save and apply a destroy plan. Query Docker by the recorded IDs and Terraform
   state to verify actual removal.
6. Plan and apply the same committed configuration again.
7. Repeat the application/network/restart checks; require new container and
   network IDs and another no-drift plan.
8. Destroy the recreated environment, confirm removal, and save `result.txt`.

Evidence is named by stage: `initial-*`, `destroy-*`, `recreated-*`, and
`cleanup-*`. `lifecycle.log` contains the full demonstration command output.
Validation logs are in the separate validation artifact. Run metadata identifies
the commit and workflow URL. The workflow preserves diagnostics on failures, so
an artifact's existence alone does not demonstrate success.

## Remaining verification checkpoint

GitHub validation passed on feature commit `fa049284749cc4158f8ce7c856465f0384d84c4a`:

- [PR validation run 42516490444](https://github.com/AbdulSharifullah/ITSD-4350-Git-Workflow/actions/runs/42516490444):
  formatting check, Terraform initialization, validation and plan passed.
- The real plan reported **3 to add, 0 to change, 0 to destroy**: application
  image, container, and dedicated network. It did not create those resources.
- Validation artifact `terraform-validation-42516490444-1` was downloaded and
  inspected. Its generated provider lock file was added to version control.
- Initial workflow setup used a runner context at a level where GitHub did not
  support it. Moving temporary-path setup into the shell step fixed the workflow.
  A formatting check then identified one spacing difference, which was corrected
  before the successful validation. No check was disabled.

[PR #10](https://github.com/AbdulSharifullah/ITSD-4350-Git-Workflow/pull/10) requires
the owner's second-account review before merging. The manual lifecycle workflow
can then run on `main`. Actual resource IDs, destruction/recreation results,
final CI status, and further troubleshooting will be recorded after execution.
This file makes no claim that the lifecycle has already passed.
