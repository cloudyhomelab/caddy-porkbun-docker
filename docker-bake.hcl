variable "REGISTRY" { default = "docker.io" }
variable "NAMESPACE"  { default = "binarycodes" }
variable "IMAGE_NAME" { default = "caddy-porkbun" }

# the caddy version is whatever the Dockerfile's FROM lines pin; the workflows
# read it from there, so an unset value fails the build on an invalid tag
variable "CADDY_VERSION" { default = "" }
variable "CADDY_PORKBUN_VERSION" { default = "v0.3.1" }

variable "LOCAL" { default = false }

group "default" {
  targets = ["image"]
}

target "image" {
  context    = "."
  dockerfile = "Dockerfile"

  args = {
    CADDY_PORKBUN_VERSION = CADDY_PORKBUN_VERSION
  }

  labels = {
    "org.opencontainers.image.title" = "caddy-porkbun"
    "org.opencontainers.image.description" = "Caddy with the Porkbun DNS provider for ACME DNS challenges"
    "org.opencontainers.image.version" = "${CADDY_VERSION}"
    "org.opencontainers.image.source" = "https://github.com/cloudyhomelab/caddy-porkbun-docker"
    "org.opencontainers.image.licenses" = "GPL-3.0-or-later"
  }

  tags = [
    "${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:${CADDY_VERSION}",
    "${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:latest",
  ]

  platforms = LOCAL ? [] : ["linux/amd64", "linux/arm64"]
}
