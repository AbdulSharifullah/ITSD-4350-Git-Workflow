output "staging_url" {
  description = "Accessible inside this runner only, while the container exists."
  value       = "https://${cidrhost(var.network_cidr, 2)}:${var.app_port}"
}

output "container_id" {
  value = docker_container.calculator.id
}

output "container_name" {
  value = docker_container.calculator.name
}

output "network_id" {
  value = docker_network.staging.id
}

output "network_name" {
  value = docker_network.staging.name
}

output "image_id" {
  value = docker_image.calculator.image_id
}
