ARG CADDY_PORKBUN_VERSION="unknown"

# Go cross-compiles, so build natively instead of under emulation
FROM --platform=$BUILDPLATFORM caddy:2.11.7-builder-alpine@sha256:ef9b65adf9a224770c6d5f6d1ae1bf99bc3caaa78d8c4bae3ea949ee6984f301 AS builder

ARG TARGETOS
ARG TARGETARCH
ARG CADDY_PORKBUN_VERSION

# the builder image sets CADDY_VERSION, so xcaddy builds the base image's caddy
RUN [ "${CADDY_PORKBUN_VERSION}" != "unknown" ] || { echo "ERROR: CADDY_PORKBUN_VERSION is not set"; exit 2; }; \
    GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" xcaddy build \
    --with "github.com/caddy-dns/porkbun@${CADDY_PORKBUN_VERSION}"


FROM caddy:2.11.7-alpine@sha256:eb4d35b7452d1ab6171fbdbe8d9275b2301dad6dad92115d91e19fb9b24d510f

# the weekly rebuild ships alpine security fixes between digest bumps
RUN apk upgrade --no-cache

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
