# caddy-porkbun-docker

[Caddy](https://caddyserver.com/) with the [Porkbun DNS provider](https://github.com/caddy-dns/porkbun)
compiled in, for ACME certificates through the DNS challenge.

Image: `docker.io/binarycodes/caddy-porkbun:<caddy-version>` (also `latest`),
built for `linux/amd64` and `linux/arm64` on the official `caddy:<version>-alpine`
image. Everything else about the image (ports, volumes, default command,
`Caddyfile` location) is what the official image documents.

## Configuration

Set a Porkbun API key pair as environment variables and reference them from the
`Caddyfile`:

```caddyfile
{
    acme_dns porkbun {
        api_key {env.PORKBUN_API_KEY}
        api_secret_key {env.PORKBUN_API_SECRET_KEY}
    }
}

example.com {
    reverse_proxy app:8080
}
```

```yaml
services:
  caddy:
    image: docker.io/binarycodes/caddy-porkbun:latest
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    environment:
      PORKBUN_API_KEY: pk1_...
      PORKBUN_API_SECRET_KEY: sk1_...
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
```

## Building

```sh
docker buildx bake                 # both platforms, tags from docker-bake.hcl
docker buildx bake --set '*.platform=linux/amd64' --load   # a local image
```

Versions live in `docker-bake.hcl`: the caddy version with the digests of its
alpine and builder images, and the porkbun plugin version. The `bump caddy and
porkbun` workflow runs `tools/bump_caddy.py` weekly and opens an auto-merging
pull request when Docker Hub or the plugin's releases moved.

## Verifying the image

Images are signed keyless with cosign from this repository's `publish.yml` on
`main`, and carry SBOM and provenance attestations:

```sh
cosign verify docker.io/binarycodes/caddy-porkbun:latest \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity https://github.com/cloudyhomelab/caddy-porkbun-docker/.github/workflows/publish.yml@refs/heads/main
```

## License

[GNU General Public License v3.0 or later](LICENSE).
