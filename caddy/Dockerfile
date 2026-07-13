# Caddy + módulo Cloudflare DNS para DNS-01 challenge
FROM caddy:2-builder AS builder
RUN caddy-builder github.com/caddy-dns/cloudflare

FROM caddy:2
COPY --from=builder /usr/bin/caddy /usr/bin/caddy