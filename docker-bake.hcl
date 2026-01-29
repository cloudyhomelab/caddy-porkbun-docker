variable "REGISTRY" { default = "docker.io" }
variable "NAMESPACE"  { default = "binarycodes" }

variable "IMAGE_NAME" { default = "caddy-porkbun" }
variable "CADDY_VERSION" { default = "2.11" }
variable "CADDY_PORKBUN_VERSION" { default = "v0.3.1" }

group "default" {
  targets = ["app"]
}

target "app" {
  context    = "."
  dockerfile = "Dockerfile"

  args = {
    CADDY_VERSION = CADDY_VERSION
    CADDY_PORKBUN_VERSION = CADDY_PORKBUN_VERSION
  }

  tags = [
    "${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:${CADDY_VERSION}",
    "${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:latest",
  ]

  platforms = ["linux/amd64"]
}
