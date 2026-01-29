variable "REGISTRY" { default = "docker.io/binarycodes" }

variable "TAG_NAME" { default = "caddy-porkbun" }
variable "CADDY_VERSION" { default = "2.11" }
variable "CADDY_PORKBUN_VERSION" { default = "v0.3.1" }

group "default" {
  targets = ["app"]
}

target "app" {
  context    = "."
  dockerfile = "Dockerfile"

  args = {
    CADDY_VERSION = "${CADDY_VERSION}"
    CADDY_PORKBUN_VERSION = "${CADDY_PORKBUN_VERSION}"
  }

  tags = [
    "${REGISTRY}/${TAG_NAME}:${CADDY_VERSION}",
    "${REGISTRY}/${TAG_NAME}:latest",
  ]

  platforms = ["linux/amd64"]
}
