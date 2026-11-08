#!/usr/bin/env bash
# Run from the repository root. Destruction is limited to this Terraform state.
set -euo pipefail
: "${TF_VAR_app_revision:?Set the checked-out Git SHA}"
: "${TF_VAR_runtime_dir:?Generate the runtime files first}"
mkdir -p infra/evidence
export SSL_CERT_FILE="$TF_VAR_runtime_dir/server.crt"

tf() { terraform -chdir=infra "$@"; }
record() { "$@" 2>&1 | tee "infra/evidence/$stage-$name.log"; }

snapshot() {
  tf output -json > "infra/evidence/$stage-outputs.json"
  local container network
  container=$(tf output -raw container_id)
  network=$(tf output -raw network_id)
  # Deliberately omit raw container configuration, runtime files and Terraform state.
  docker inspect "$container" | jq '.[0] | {
    Id, Image, State, Config: {User: .Config.User, Labels: .Config.Labels},
    HostConfig: {PortBindings: .HostConfig.PortBindings,
      ReadonlyRootfs: .HostConfig.ReadonlyRootfs, CapDrop: .HostConfig.CapDrop,
      SecurityOpt: .HostConfig.SecurityOpt},
    NetworkSettings: {Networks: .NetworkSettings.Networks}
  }' > "infra/evidence/$stage-container.json"
  docker network inspect "$network" | jq '.[0] | {
    Id, Name, Driver, Internal, IPAM, Labels, Containers
  }' > "infra/evidence/$stage-network.json"
  docker logs "$container" > "infra/evidence/$stage-application.log" 2>&1
}

verify() {
  local container network url
  container=$(tf output -raw container_id)
  network=$(tf output -raw network_id)
  url=$(tf output -raw staging_url)
  name=smoke-test
  record python smoke_test.py "$url" "$TF_VAR_app_revision" --attempts 12
  curl --fail --silent --show-error --cacert "$SSL_CERT_FILE" \
    "$url/health" | tee "infra/evidence/$stage-health.json"
  curl --fail --silent --show-error --cacert "$SSL_CERT_FILE" \
    "$url/" > "infra/evidence/$stage-calculator.html"
  docker inspect "$container" | jq -e '.[0] |
    .State.Running == true and .Config.User == "10001:10001" and
    .HostConfig.ReadonlyRootfs == true and
    ([.HostConfig.PortBindings[][] | .HostIp] == ["127.0.0.1"])' >/dev/null
  docker network inspect "$network" | jq -e '.[0].Internal == true' >/dev/null
  # Exercise actual egress rather than relying solely on a configuration flag.
  docker exec "$container" python -c $'import socket\ntry:\n socket.create_connection(("1.1.1.1",443),timeout=3).close()\nexcept OSError:\n print("PASS: direct external TCP egress blocked")\nelse:\n raise SystemExit("FAIL: unexpected external TCP access")' \
    | tee "infra/evidence/$stage-network-test.log"
  # Check the service restarts after an actual container restart.
  docker restart "$container" >/dev/null
  name=after-restart
  record python smoke_test.py "$url" "$TF_VAR_app_revision" --attempts 12
  snapshot
  echo "PASS: running non-root service; loopback-only HTTPS; internal network; restart verified."
}

assert_absent() {
  local container="$1" network="$2" image="$3"
  if docker container inspect "$container" >/dev/null 2>&1; then
    echo 'FAIL: container still exists'; return 1
  fi
  if docker network inspect "$network" >/dev/null 2>&1; then
    echo 'FAIL: network still exists'; return 1
  fi
  if docker image inspect "$image" >/dev/null 2>&1; then
    echo 'FAIL: application image still exists'; return 1
  fi
  [[ -z "$(tf state list)" ]]
  echo 'PASS: container, dedicated network, application image and managed state resources removed.'
}

stage=initial
name=plan
record tf plan -input=false -out=staging.tfplan
name=apply
record tf apply -input=false -auto-approve staging.tfplan
verify
initial_container=$(tf output -raw container_id)
initial_network=$(tf output -raw network_id)
initial_image=$(tf output -raw image_id)
name=no-drift
# Exit 2 means drift exists; pipefail prevents a false success.
record tf plan -input=false -detailed-exitcode

stage=destroy
name=plan
record tf plan -destroy -input=false -out=destroy.tfplan
name=apply
record tf apply -input=false -auto-approve destroy.tfplan
name=absence
record assert_absent "$initial_container" "$initial_network" "$initial_image"

stage=recreated
name=plan
record tf plan -input=false -out=staging.tfplan
name=apply
record tf apply -input=false -auto-approve staging.tfplan
verify
[[ "$initial_container" != "$(tf output -raw container_id)" ]]
[[ "$initial_network" != "$(tf output -raw network_id)" ]]
name=no-drift
record tf plan -input=false -detailed-exitcode

stage=cleanup
name=destroy
final_container=$(tf output -raw container_id)
final_network=$(tf output -raw network_id)
final_image=$(tf output -raw image_id)
record tf destroy -input=false -auto-approve
name=absence
record assert_absent "$final_container" "$final_network" "$final_image"
printf 'PASS: apply, HTTPS calculator tests, restart, no drift, destroy, absence, recreate, repeat tests, final cleanup.\nRevision: %s\nRun: %s/%s/actions/runs/%s\n' \
  "$TF_VAR_app_revision" "$GITHUB_SERVER_URL" "$GITHUB_REPOSITORY" "$GITHUB_RUN_ID" \
  | tee infra/evidence/result.txt
