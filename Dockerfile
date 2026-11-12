ARG CADDY_PORKBUN_VERSION="unknown"

# Go cross-compiles, so build natively instead of under emulation
FROM --platform=$BUILDPLATFORM caddy:2.11.8-builder-alpine@sha256:e42a64b3bc70aa3a1387bde85b930e507a378fecae5852d5bfde9dcd37d0b999 AS builder

ARG TARGETOS
ARG TARGETARCH
ARG CADDY_PORKBUN_VERSION

# the builder image sets CADDY_VERSION, so xcaddy builds the base image's caddy
RUN [ "${CADDY_PORKBUN_VERSION}" != "unknown" ] || { echo "ERROR: CADDY_PORKBUN_VERSION is not set"; exit 2; }; \
    GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" xcaddy build \
    --with "github.com/caddy-dns/porkbun@${CADDY_PORKBUN_VERSION}"


FROM caddy:2.11.9-alpine@sha256:0bbb055bda6793c999bde78b1b5ce3e89f829fb031af2cf50056ea1246559fee

# the weekly rebuild ships alpine security fixes between digest bumps
RUN apk upgrade --no-cache

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
