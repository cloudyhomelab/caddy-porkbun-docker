variable "REGISTRY" { default = "docker.io" }
variable "NAMESPACE"  { default = "binarycodes" }
variable "IMAGE_NAME" { default = "caddy-porkbun" }

# bump_caddy.py moves these three together; the digests are the index digests of
# caddy:<version>-alpine and caddy:<version>-builder-alpine
variable "CADDY_VERSION" { default = "2.11.4" }
variable "CADDY_DIGEST"         { default = "sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648" }
variable "CADDY_BUILDER_DIGEST" { default = "sha256:1a1689db91cfb390b2d856a1b3774e796852822cd723fa54c475b272f82bb4b7" }
variable "CADDY_PORKBUN_VERSION" { default = "v0.3.1" }

variable "LOCAL" { default = false }

group "default" {
  targets = ["image"]
}

target "image" {
  context    = "."
  dockerfile = "Dockerfile"

  args = {
    CADDY_IMAGE = "caddy:${CADDY_VERSION}-alpine@${CADDY_DIGEST}"
    CADDY_BUILDER_IMAGE = "caddy:${CADDY_VERSION}-builder-alpine@${CADDY_BUILDER_DIGEST}"
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
