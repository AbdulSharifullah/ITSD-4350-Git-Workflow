locals {
  name = "itsd-4350-${var.environment}"
  labels = {
    project     = "itsd-4350-mini-project-2-2"
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "docker_network" "staging" {
  name     = "${local.name}-network"
  driver   = "bridge"
  internal = true
  ipam_config {
    subnet = var.network_cidr
  }
  dynamic "labels" {
    for_each = local.labels
    content {
      label = labels.key
      value = labels.value
    }
  }
}

resource "docker_image" "calculator" {
  name         = "${local.name}:${var.app_revision}"
  keep_locally = false
  build {
    context = abspath("${path.module}/..")
    build_args = {
      APP_REVISION = var.app_revision
    }
  }
  triggers = {
    revision = var.app_revision
  }
}

resource "docker_container" "calculator" {
  name      = local.name
  image     = docker_image.calculator.image_id
  restart   = "unless-stopped"
  read_only = true
  memory    = 256
  env = [
    "APP_ENV=staging",
    "APP_REVISION=${var.app_revision}",
    "PORT=${var.app_port}",
  ]
  # Read the generated session key at runtime, keeping it out of Terraform state.
  command = [
    "sh", "-c",
    "set -a; . /run/staging/runtime.env; exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --certfile /run/staging/server.crt --keyfile /run/staging/server.key --access-logfile - --error-logfile - app:app",
  ]
  capabilities {
    drop = ["ALL"]
  }
  security_opts = ["no-new-privileges:true"]
  tmpfs = {
    "/tmp" = "rw,noexec,nosuid,size=64m"
  }
  volumes {
    host_path      = var.runtime_dir
    container_path = "/run/staging"
    read_only      = true
  }
  networks_advanced {
    name = docker_network.staging.name
  }
  ports {
    internal = var.app_port
    external = var.host_port
    ip       = "127.0.0.1"
    protocol = "tcp"
  }
  dynamic "labels" {
    for_each = local.labels
    content {
      label = labels.key
      value = labels.value
    }
  }
}
