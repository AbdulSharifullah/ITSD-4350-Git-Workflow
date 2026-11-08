terraform {
  required_version = "~> 1.13.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "= 3.6.2"
    }
  }
}
