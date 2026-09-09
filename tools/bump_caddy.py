#!/usr/bin/env python3
"""Move docker-bake.hcl to the latest caddy image and caddy-dns/porkbun release.

The base images are pinned by digest, so upstream rebuilds of the same caddy version
also count as a bump.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

CADDY_TAGS_URL = "https://hub.docker.com/v2/repositories/library/caddy/tags?name=alpine&page_size=100"
PORKBUN_RELEASES_URL = "https://api.github.com/repos/caddy-dns/porkbun/releases/latest"
BAKE_FILE = Path(__file__).resolve().parent.parent / "docker-bake.hcl"

# the runtime and builder images share the caddy version; both digests move independently
IMAGE_TAG = re.compile(r"^(?P<version>\d+\.\d+\.\d+)-(?P<flavour>alpine|builder-alpine)$")
RELEASE_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ApiError(Exception):
    pass


class BakeError(Exception):
    pass


@dataclass(frozen=True)
class Upstream:
    caddy_version: str
    caddy_digest: str
    caddy_builder_digest: str
    porkbun_version: str

    def bake_variables(self) -> dict[str, str]:
        return {
            "CADDY_VERSION": self.caddy_version,
            "CADDY_DIGEST": self.caddy_digest,
            "CADDY_BUILDER_DIGEST": self.caddy_builder_digest,
            "CADDY_PORKBUN_VERSION": self.porkbun_version,
        }


def _get_json(url: str, headers: Mapping[str, str]) -> object:
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace").strip()
        raise ApiError(f"GET {url} returned HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise ApiError(f"GET {url} failed: {error.reason}") from error


def _hub_pages(url: str | None) -> Iterator[Mapping]:
    while url:
        page = _get_json(url, {"Accept": "application/json"})
        if not isinstance(page, Mapping):
            raise ApiError(f"GET {url} returned no tag page")
        yield page
        url = page.get("next")


def latest_caddy_image(pages: Iterator[Mapping]) -> tuple[str, str, str]:
    """Return (version, digest, builder digest) of the newest caddy version with both alpine images."""
    digests: dict[tuple[str, str], str] = {}
    for page in pages:
        for tag in page.get("results") or []:
            match = IMAGE_TAG.match(tag.get("name") or "")
            digest = tag.get("digest") or ""
            if match and DIGEST.match(digest):
                digests[match["version"], match["flavour"]] = digest
    complete = {
        version for version, flavour in digests if flavour == "alpine" and (version, "builder-alpine") in digests
    }
    if not complete:
        raise ApiError("Docker Hub lists no caddy version with both an alpine and a builder-alpine image")
    version = max(complete, key=lambda v: tuple(int(part) for part in v.split(".")))
    return version, digests[version, "alpine"], digests[version, "builder-alpine"]


def latest_porkbun_release(payload: object) -> str:
    tag = payload.get("tag_name", "") if isinstance(payload, Mapping) else ""
    if not RELEASE_TAG.match(tag):
        raise ApiError(f"unexpected caddy-dns/porkbun release tag {tag!r}")
    return tag


def fetch_upstream(token: str | None = None) -> Upstream:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    version, digest, builder_digest = latest_caddy_image(_hub_pages(CADDY_TAGS_URL))
    porkbun = latest_porkbun_release(_get_json(PORKBUN_RELEASES_URL, headers))
    return Upstream(version, digest, builder_digest, porkbun)


def _default_pattern(name: str) -> re.Pattern:
    return re.compile(rf'^(variable\s+"{re.escape(name)}"\s*\{{\s*default\s*=\s*")([^"]*)(")', re.MULTILINE)


def read_variable(text: str, name: str) -> str:
    matches = _default_pattern(name).findall(text)
    if len(matches) != 1:
        raise BakeError(f"expected exactly one variable {name!r} with a default, found {len(matches)}")
    return matches[0][1]


def set_variable(text: str, name: str, value: str) -> str:
    read_variable(text, name)
    return _default_pattern(name).sub(lambda match: f"{match.group(1)}{value}{match.group(3)}", text)


def describe(previous: Mapping[str, str], upstream: Upstream) -> str:
    """One short phrase per component that moved, for the commit subject."""
    changes = []
    if previous["CADDY_VERSION"] != upstream.caddy_version:
        changes.append(f"caddy {previous['CADDY_VERSION']} -> {upstream.caddy_version}")
    elif (previous["CADDY_DIGEST"], previous["CADDY_BUILDER_DIGEST"]) != (
        upstream.caddy_digest,
        upstream.caddy_builder_digest,
    ):
        changes.append(f"caddy {upstream.caddy_version} image digests")
    if previous["CADDY_PORKBUN_VERSION"] != upstream.porkbun_version:
        changes.append(f"porkbun {previous['CADDY_PORKBUN_VERSION']} -> {upstream.porkbun_version}")
    return ", ".join(changes)


def bump(bake_file: Path, upstream: Upstream) -> str:
    """Rewrite the bake file for `upstream`; return what changed, or "" when already there."""
    text = bake_file.read_text()
    wanted = upstream.bake_variables()
    previous = {name: read_variable(text, name) for name in wanted}
    if previous == wanted:
        return ""
    for name, value in wanted.items():
        text = set_variable(text, name, value)
    bake_file.write_text(text)
    return describe(previous, upstream)


def main(argv: Sequence[str]) -> int:
    bake_file = Path(argv[0]) if argv else BAKE_FILE
    try:
        upstream = fetch_upstream(os.environ.get("GITHUB_TOKEN"))
        changes = bump(bake_file, upstream)
    except (ApiError, BakeError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    if not changes:
        print(
            f"{bake_file.name} is already at caddy {upstream.caddy_version}, porkbun {upstream.porkbun_version}",
            file=sys.stderr,
        )
        return 0
    print(f"{bake_file.name}: {changes}", file=sys.stderr)
    print(changes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
