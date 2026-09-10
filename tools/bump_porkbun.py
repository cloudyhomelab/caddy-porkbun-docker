#!/usr/bin/env python3
"""Move docker-bake.hcl to the latest caddy-dns/porkbun release.

Dependabot follows the caddy base images in the Dockerfile, but the plugin is an
xcaddy --with argument that no package ecosystem tracks.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path

RELEASES_URL = "https://api.github.com/repos/caddy-dns/porkbun/releases/latest"
BAKE_FILE = Path(__file__).resolve().parent.parent / "docker-bake.hcl"
VARIABLE = "CADDY_PORKBUN_VERSION"

TAG = re.compile(r"^v\d+\.\d+\.\d+$")


class ApiError(Exception):
    pass


class BakeError(Exception):
    pass


def parse_release(payload: object) -> str:
    """Return the release tag with its v prefix, which is what xcaddy --with takes."""
    tag = payload.get("tag_name", "") if isinstance(payload, Mapping) else ""
    if not TAG.match(tag):
        raise ApiError(f"unexpected release tag {tag!r}")
    return tag


def fetch_latest_release(token: str | None = None) -> str:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(RELEASES_URL, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return parse_release(json.load(response))
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace").strip()
        raise ApiError(f"GET {RELEASES_URL} returned HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise ApiError(f"GET {RELEASES_URL} failed: {error.reason}") from error


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


def bump(bake_file: Path, version: str) -> str | None:
    """Rewrite the bake file for `version`; return the previous version, or None when already there."""
    text = bake_file.read_text()
    current = read_variable(text, VARIABLE)
    if current == version:
        return None
    bake_file.write_text(set_variable(text, VARIABLE, version))
    return current


def main(argv: Sequence[str]) -> int:
    bake_file = Path(argv[0]) if argv else BAKE_FILE
    try:
        version = fetch_latest_release(os.environ.get("GITHUB_TOKEN"))
        previous = bump(bake_file, version)
    except (ApiError, BakeError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    if previous is None:
        print(f"{bake_file.name} is already at porkbun {version}", file=sys.stderr)
        return 0
    print(f"{bake_file.name}: porkbun {previous} -> {version}", file=sys.stderr)
    print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
