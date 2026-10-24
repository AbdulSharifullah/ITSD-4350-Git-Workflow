# Workflow and review standards

Repository: https://github.com/AbdulSharifullah/ITSD-4350-Git-Workflow

## Trunk-based development with short-lived feature branches

1. Update `main`, then create `feature/<description>`, `fix/<description>`,
   `docs/<description>`, or `ci/<description>` using lowercase hyphenated names.
2. Install requirements-dev.txt and run `git config core.hooksPath hooks`.
3. Make focused commits using `type: description` or `type(scope): description`.
   Types: feat, fix, docs, test, ci, chore, refactor. Keep descriptions 3–72 characters.
4. Push the branch. Every push runs lint, tests, compilation, and packaging.
5. Open a PR into `main`, use the same title convention, and fill in the template.
   PR CI also validates the branch name, title, and new non-merge commit subjects.
6. An independent reviewer checks correctness, tests, scope, and documentation.
   Address feedback and obtain one actual approval. Do not self-approve.
7. Merge only after approval and passing checks. Use the compliant PR title for
   a squash commit, then update your local `main`.

## Repository enforcement

The earlier mini-project documentation records that `main` requires one approval.
That server setting must be verified in Settings > Branches/Rules; documentation
alone does not enforce it. Configure `main` to require a PR, one approval, dismissal
of stale approvals, and required checks `build-and-test` and `standards` after
those checks first run. Apply rules to administrators where available.

Local hooks enforce lint/tests/build and commit subjects. GitHub Actions enforces
PR naming and new commit subjects through the `standards` job. The PR template
records validation and review expectations. Existing historical branch names and
commits are retained as part of Mini Projects 1.1–1.4.
