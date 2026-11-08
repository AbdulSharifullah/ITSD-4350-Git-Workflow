#!/usr/bin/env bash
# This script never prints the generated private key or Flask session secret.
set -euo pipefail
: "${TF_VAR_runtime_dir:?Set TF_VAR_runtime_dir to a temporary absolute directory}"
mkdir -p "$TF_VAR_runtime_dir"
chmod 755 "$TF_VAR_runtime_dir"
app_ip=$(terraform -chdir=infra console <<< 'cidrhost(var.network_cidr, 2)' | jq -er .)
openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 1 \
  -subj '/CN=calculator-staging' -addext "subjectAltName=IP:$app_ip" \
  -keyout "$TF_VAR_runtime_dir/server.key" \
  -out "$TF_VAR_runtime_dir/server.crt" 2>/dev/null
python - <<'PY'
import os
from pathlib import Path
import secrets
path = Path(os.environ['TF_VAR_runtime_dir']) / 'runtime.env'
path.write_text('SECRET_KEY=' + secrets.token_hex(32) + '\n')
PY
chmod 644 "$TF_VAR_runtime_dir/server.crt"
chmod 400 "$TF_VAR_runtime_dir/server.key" "$TF_VAR_runtime_dir/runtime.env"
# The existing Dockerfile runs as UID 10001. Only that UID can read these files.
sudo chown 10001:10001 "$TF_VAR_runtime_dir/server.key" "$TF_VAR_runtime_dir/runtime.env"
echo 'Generated one-day staging TLS certificate and private runtime configuration.'
