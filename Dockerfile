ARG CADDY_PORKBUN_VERSION="unknown"

# Go cross-compiles, so build natively instead of under emulation
FROM --platform=$BUILDPLATFORM caddy:2.11.4-builder-alpine@sha256:0aa610043dab5da82ad0a0268e46bb852785e6f5160f12f1c6fe3f42903d7e1b AS builder

ARG TARGETOS
ARG TARGETARCH
ARG CADDY_PORKBUN_VERSION

# the builder image sets CADDY_VERSION, so xcaddy builds the base image's caddy
RUN [ "${CADDY_PORKBUN_VERSION}" != "unknown" ] || { echo "ERROR: CADDY_PORKBUN_VERSION is not set"; exit 2; }; \
    GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" xcaddy build \
    --with "github.com/caddy-dns/porkbun@${CADDY_PORKBUN_VERSION}"


FROM caddy:2.11.4-alpine@sha256:6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b

# the weekly rebuild ships alpine security fixes between digest bumps
RUN apk upgrade --no-cache

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
