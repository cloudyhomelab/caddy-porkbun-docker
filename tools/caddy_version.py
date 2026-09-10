#!/usr/bin/env python3
"""Print the caddy version pinned by the Dockerfile's FROM lines.

The image tag is the caddy version, which lives only in the Dockerfile; the workflows
feed the output to bake as CADDY_VERSION.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parent.parent / "Dockerfile"

# every caddy image, builder included, must carry a digest; the version is whatever
# precedes the flavour suffix
FROM_CADDY = re.compile(r"^FROM\s+(?:--platform=\S+\s+)?caddy:(?P<ref>\S+)", re.MULTILINE)
PINNED = re.compile(r"^(?P<version>\d+\.\d+\.\d+)(?:-[a-z0-9.-]+)?@sha256:[0-9a-f]{64}$")


class DockerfileError(Exception):
    pass


def caddy_version(text: str) -> str:
    refs = [match["ref"] for match in FROM_CADDY.finditer(text)]
    if not refs:
        raise DockerfileError("no FROM line uses a caddy image")
    versions = set()
    for ref in refs:
        match = PINNED.match(ref)
        if not match:
            raise DockerfileError(f"caddy:{ref} is not pinned as <version>[-flavour]@sha256:<digest>")
        versions.add(match["version"])
    if len(versions) != 1:
        raise DockerfileError(f"the FROM lines pin different caddy versions: {' '.join(sorted(versions))}")
    return versions.pop()


def main(argv: Sequence[str]) -> int:
    dockerfile = Path(argv[0]) if argv else DOCKERFILE
    try:
        print(caddy_version(dockerfile.read_text()))
    except (DockerfileError, OSError) as error:
        print(f"{dockerfile}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
