variable "environment" {
  description = "Short environment name used in Docker resource names."
  type        = string
  default     = "staging"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,30}$", var.environment))
    error_message = "Use 1-31 lowercase letters, digits or hyphens; start with a letter."
  }
}

variable "app_revision" {
  description = "Full Git commit SHA checked out by the workflow."
  type        = string
  validation {
    condition     = can(regex("^[a-f0-9]{40}$", var.app_revision))
    error_message = "Supply the full 40-character Git commit SHA."
  }
}

variable "network_cidr" {
  description = "Dedicated private IPv4 subnet; must not overlap another Docker network."
  type        = string
  default     = "172.28.22.0/24"
  validation {
    condition = can(cidrnetmask(var.network_cidr)) && can(regex(
      "^(10\\.|192\\.168\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.)", var.network_cidr
    )) && can(regex("/(2[0-9])$", var.network_cidr))
    error_message = "Use a private IPv4 subnet with prefix /20 through /29."
  }
}

variable "host_port" {
  description = "HTTPS port published on runner loopback only."
  type        = number
  default     = 8443
  validation {
    condition     = var.host_port >= 1024 && var.host_port <= 65535 && floor(var.host_port) == var.host_port
    error_message = "Use an integer port from 1024 through 65535."
  }
}

variable "app_port" {
  description = "Unprivileged Gunicorn HTTPS port inside the container."
  type        = number
  default     = 10000
  validation {
    condition     = var.app_port >= 1024 && var.app_port <= 65535 && floor(var.app_port) == var.app_port
    error_message = "Use an integer port from 1024 through 65535."
  }
}

variable "runtime_dir" {
  description = "Absolute runner directory containing runtime.env, server.crt and server.key; contents stay outside Terraform."
  type        = string
  validation {
    condition     = startswith(var.runtime_dir, "/")
    error_message = "Supply an absolute Linux directory path."
  }
}
