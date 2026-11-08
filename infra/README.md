# Mini Project 2.2 — Terraform staging environment

Repository: https://github.com/AbdulSharifullah/ITSD-4350-Git-Workflow

## Purpose and scope

Terraform provisions a real Linux application container and its network on a
standard GitHub-hosted Ubuntu runner. GitHub Actions tests the calculator,
destroys staging, confirms removal, recreates it, repeats the tests, and cleans
up. There is no AWS account, paid hosting, local installation, or self-hosted
runner. Staging exists during the workflow; the saved evidence remains afterward.
It is not an externally accessible or persistent website. The existing Render
deployment continues to serve that purpose.

The existing Flask calculator is reused without application changes. It has no
persistent data or database dependency, so no database is provisioned. The
existing Dockerfile installs hash-locked dependencies and runs Gunicorn as UID
10001. The existing application tests, CI workflow, SonarCloud integration, and
Render delivery workflow are preserved.

## Architecture

See [architecture.mmd](architecture.mmd) for the maintainable diagram and
[architecture.svg](architecture.svg) for the rendered image.

The runner hosts Terraform, Docker Engine, and the test client. Terraform creates
three resources: an image built from the checked-out Git revision, a dedicated
internal bridge network, and the application container. The Dockerfile is the
runtime definition; Terraform manages its deployment and networking. Gunicorn
serves HTTPS directly, avoiding an extra proxy container. The container restarts
automatically while the Docker host exists. A real container restart is tested.
This does not simulate a host reboot.

Networking rules are explicit: publish only one TCP port on `127.0.0.1`, attach
the container to the dedicated subnet, and mark that network internal to block
direct external routing. No SSH, public listener, remote Docker socket, or cloud
firewall is needed. Both the bindings and an actual outbound connection attempt
are tested. Package downloads occur during the image build, before runtime
network isolation is applied. The application runs with a read-only root
filesystem, a writable temporary directory, and dropped Linux capabilities.

The job generates a one-day self-signed localhost certificate and a random Flask
session key outside the repository. Private files are readable only by the
container's UID and mounted read-only. The test client explicitly trusts that
certificate; certificate verification and secure cookies stay enabled. These
files are not Terraform variables, state values, source files, or artifacts.

## Rubric mapping

| Requirement | Implementation / evidence |
|---|---|
| Approved IaC tool | Terraform 1.13.5 and pinned Docker provider |
| Application server | Actual Flask/Gunicorn Linux container, built from this repository |
| Networking and security | Dedicated internal subnet, loopback-only HTTPS binding; inspect and egress tests |
| Parameterization | Environment, commit, subnet, host/container ports, runtime path; validated inputs |
| Modularity | Separate provider, version, resource, variable and output files in one Terraform root module |
| Version control | `feature/staging-terraform-iac`, conventional commits, reviewed PR into protected `main` |
| CD integration | New `Terraform Staging` workflow; existing application CI and Render CD retained |
| Automated validation | Formatting, initialization, validation, plan, shell syntax checks |
| Reproducibility | Actual apply/test/destroy/removal/recreate/test/cleanup sequence |
| Professional documentation | This guide, diagram and reproducibility report |

One small root module keeps the configuration reusable without adding wrapper
modules that would only forward variables.

## Run without installing anything locally

After the feature PR is approved and merged:

1. Open repository **Actions → Terraform Staging → Run workflow**.
2. Select `main` and confirmation `recreate-and-cleanup`.
3. Run the workflow. This explicitly authorizes creation and destruction of only
   the temporary staging resources in that runner.
4. Inspect `validate` and `demonstrate`. A green validation job alone does not
   prove that staging was created.
5. Download `terraform-validation-<run>-<attempt>` and
   `terraform-lifecycle-<run>-<attempt>` from the completed run's Artifacts section.
   Download within 14 days and retain them with the submission.

PRs and feature pushes only run non-provisioning validation. They cannot run the
demonstration job. The lifecycle job requires a manual dispatch on `main` after
the normal branch review process. The manual confirmation includes the required
destruction, recreation, and final cleanup. No credentials or additional GitHub
repository secrets are needed. Only read access to repository contents is
requested. Standard Linux runners in this public repository have no compute
charge; small diagnostic artifacts are retained for 14 days.

The workflow is independent of Render and never triggers its deployment API.
An eventual merge still invokes the existing application's normal CI/CD process.

## State and cleanup

Terraform's local backend is appropriate here because each job owns a completely
temporary environment and performs the whole lifecycle in that same job. State
is never handed between jobs, committed, or uploaded. This is not a persistent
deployment on an ephemeral runner. The always-run cleanup step retries Terraform
destruction after failures, and GitHub discards the job VM afterward. A cleanup
failure fails the job rather than being hidden.

The provider dependency lock file is committed. Workflow initialization uses
`-lockfile=readonly` so unexpected provider selection changes fail visibly.

The three Terraform resources belong only to this project. Destruction uses its
state, not global Docker pruning. The script verifies that the application image,
container, network, and managed state entries are absent. Base-image layers and
build caches may remain until GitHub discards the VM; those are not staging
services. No staging resources remain running after a successful demonstration.

## Configuration and optional Linux reproduction

No local reproduction is required for the runner approach. On an **already
available** Linux host with Docker Engine, Terraform 1.13.x, Python 3, OpenSSL,
`curl`, `jq`, Bash and sudo, the same commands can reproduce the environment:

```bash
export TF_VAR_app_revision=$(git rev-parse HEAD)
export TF_VAR_runtime_dir=$(mktemp -d)
bash infra/prepare-runtime.sh
terraform -chdir=infra init
terraform -chdir=infra fmt -check
terraform -chdir=infra validate
terraform -chdir=infra plan
terraform -chdir=infra apply
SSL_CERT_FILE="$TF_VAR_runtime_dir/server.crt" \
  python smoke_test.py https://localhost:8443 "$TF_VAR_app_revision"
terraform -chdir=infra destroy
```

`terraform.tfvars.example` shows optional overrides. Export `TF_VAR_environment`,
`TF_VAR_network_cidr`, `TF_VAR_host_port`, or `TF_VAR_app_port`, or copy the example
to an ignored `.tfvars` file. Keep app revision equal to the actual checkout.
Use a non-overlapping private subnet. Outputs expose the URL and resource IDs.
Runtime files must remain available until destruction. On a persistent Linux
host, remove only the generated temporary directory after cleanup; keep any
remaining state until its resources have been destroyed.

## Verification and troubleshooting

`demonstrate.sh` checks health and the exact deployed commit, `5 + 3 = 8`, rejection
of invalid input, rejection of missing CSRF, resource existence, network rules,
restart recovery, no-drift plans, real removal, changed container/network IDs
after recreation, and final cleanup. It saves genuine command output and safe
resource snapshots. It does not upload raw state, plan binaries, session keys,
private keys, or full container inspection data.

- Terraform errors: inspect validation/plan logs before attempting an apply.
- Image build errors: inspect the lifecycle log and dependency-download output.
- HTTPS or CSRF failures: inspect application logs, the certificate SAN, and
  `SSL_CERT_FILE`. Keep staging cookie security enabled.
- Service errors: `docker logs $(terraform -chdir=infra output -raw container_id)`.
- Container state: `docker ps -a` and the saved safe container snapshot.
- Subnet/port collision on another Linux host: adjust the corresponding input.
- Failed cleanup: inspect `always-cleanup.log`; do not call a failed run complete.

## Technical reflection

Terraform fits this assignment because it expresses the application deployment
and network as versioned resources with a plan/apply/destroy lifecycle. Docker
provides real infrastructure without cloud billing or a separate server setup.
Git review makes infrastructure changes visible before they are merged, and
GitHub Actions executes the same configuration consistently.

Declarative configuration and no-change plans help identify configuration drift.
Recreating from a committed revision tests whether the environment can be
recovered from code instead of relying on undocumented manual setup. The report
records the actual outcome; syntax validation alone is insufficient.

The main limitation is that runner staging ends with the job. It is useful for
reproducibility and integration testing, while Render remains the persistent
staging site. Rebuilding at a much later date may also change the existing
Dockerfile's floating Python base image; pinning that digest would improve
long-term reproducibility but is outside this change's application scope.

## Evidence status

See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for the baseline, verification
procedure and initial workflow links. A successful lifecycle artifact contains
`REPRODUCIBILITY-RESULTS.md`, generated from that run's observed IDs and tests.
That generated report records the actual demonstration outcome. Do not describe
the assignment as complete until its lifecycle run and required PR review have
succeeded.

## References

- [Terraform Docker tutorial](https://developer.hashicorp.com/terraform/tutorials/docker-get-started/docker-build)
- [Docker provider](https://registry.terraform.io/providers/kreuzwerker/docker/3.6.2/docs)
- [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub Actions billing](https://docs.github.com/en/actions/concepts/billing-and-usage)
