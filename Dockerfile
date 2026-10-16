ARG CADDY_PORKBUN_VERSION="unknown"

# Go cross-compiles, so build natively instead of under emulation
FROM --platform=$BUILDPLATFORM caddy:2.11.7-builder-alpine@sha256:d6161a2c82fd58b3205048958fb6246d0c5d892beee8a47e90944610c4efd100 AS builder

ARG TARGETOS
ARG TARGETARCH
ARG CADDY_PORKBUN_VERSION

# the builder image sets CADDY_VERSION, so xcaddy builds the base image's caddy
RUN [ "${CADDY_PORKBUN_VERSION}" != "unknown" ] || { echo "ERROR: CADDY_PORKBUN_VERSION is not set"; exit 2; }; \
    GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" xcaddy build \
    --with "github.com/caddy-dns/porkbun@${CADDY_PORKBUN_VERSION}"


FROM caddy:2.11.7-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f

# the weekly rebuild ships alpine security fixes between digest bumps
RUN apk upgrade --no-cache

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
