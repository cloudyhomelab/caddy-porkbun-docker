# docker-bake.hcl pins both images to a version and digest; bare docker builds float
ARG CADDY_IMAGE="caddy:alpine"
ARG CADDY_BUILDER_IMAGE="caddy:builder-alpine"
ARG CADDY_PORKBUN_VERSION="unknown"

# Go cross-compiles, so build natively instead of under emulation
FROM --platform=$BUILDPLATFORM ${CADDY_BUILDER_IMAGE} AS builder

ARG TARGETOS
ARG TARGETARCH
ARG CADDY_PORKBUN_VERSION

# the builder image sets CADDY_VERSION, so xcaddy builds the base image's caddy
RUN [ "${CADDY_PORKBUN_VERSION}" != "unknown" ] || { echo "ERROR: CADDY_PORKBUN_VERSION is not set"; exit 2; }; \
    GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" xcaddy build \
    --with "github.com/caddy-dns/porkbun@${CADDY_PORKBUN_VERSION}"


FROM ${CADDY_IMAGE}

# the weekly rebuild ships alpine security fixes between digest bumps
RUN apk upgrade --no-cache

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
