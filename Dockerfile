ARG CADDY_VERSION="unknown"
ARG CADDY_PORKBUN_VERSION="unknown"

FROM caddy:${CADDY_VERSION}-builder-alpine AS builder
ARG CADDY_PORKBUN_VERSION

RUN xcaddy build \
    --with github.com/caddy-dns/porkbun@${CADDY_PORKBUN_VERSION}

FROM caddy:${CADDY_VERSION}-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
