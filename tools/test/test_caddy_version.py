from pathlib import Path

import pytest

import caddy_version

DIGEST = "sha256:" + "a" * 64
DOCKERFILE = f"""ARG CADDY_PORKBUN_VERSION="unknown"

FROM --platform=$BUILDPLATFORM caddy:2.11.4-builder-alpine@{DIGEST} AS builder
RUN xcaddy build

FROM caddy:2.11.4-alpine@{DIGEST}
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
"""


class TestCaddyVersion:
    def test_reads_the_version_shared_by_both_stages(self):
        assert caddy_version.caddy_version(DOCKERFILE) == "2.11.4"

    @pytest.mark.parametrize(
        "ref", [f"2.11.4@{DIGEST}", f"2.11.4-debian@{DIGEST}", f"2.11.4-windowsservercore-ltsc2022@{DIGEST}"]
    )
    def test_accepts_any_flavour(self, ref):
        assert caddy_version.caddy_version(f"FROM caddy:{ref}\n") == "2.11.4"

    @pytest.mark.parametrize(
        "ref", ["2.11.4-alpine", "2.11-alpine@" + DIGEST, "alpine@" + DIGEST, "2.11.4-alpine@sha256:abc"]
    )
    def test_requires_a_full_version_and_a_digest(self, ref):
        with pytest.raises(caddy_version.DockerfileError, match="not pinned"):
            caddy_version.caddy_version(f"FROM caddy:{ref}\n")

    def test_rejects_stages_that_pin_different_versions(self):
        text = DOCKERFILE.replace("2.11.4-alpine", "2.11.3-alpine")
        with pytest.raises(caddy_version.DockerfileError, match="different caddy versions: 2.11.3 2.11.4"):
            caddy_version.caddy_version(text)

    def test_requires_a_caddy_image(self):
        with pytest.raises(caddy_version.DockerfileError, match="no FROM line"):
            caddy_version.caddy_version(f"FROM alpine:3.22@{DIGEST}\n")

    def test_ignores_caddy_outside_from_lines(self):
        text = f"# caddy:9.9.9@{DIGEST}\nFROM caddy:2.11.4-alpine@{DIGEST}\nCOPY --from=caddy:1.0.0 /x /x\n"
        assert caddy_version.caddy_version(text) == "2.11.4"

    def test_parses_the_repository_dockerfile(self):
        text = (Path(__file__).parents[2] / "Dockerfile").read_text()
        assert caddy_version.PINNED.match(caddy_version.caddy_version(text) + "@" + DIGEST)


class TestMain:
    def test_prints_the_version(self, tmp_path, capsys):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(DOCKERFILE)
        assert caddy_version.main([str(dockerfile)]) == 0
        assert capsys.readouterr().out == "2.11.4\n"

    def test_reports_an_unpinned_image_on_stderr(self, tmp_path, capsys):
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM caddy:alpine\n")
        assert caddy_version.main([str(dockerfile)]) == 1
        out, err = capsys.readouterr()
        assert out == ""
        assert "not pinned" in err

    def test_missing_dockerfile_exits_1(self, tmp_path, capsys):
        assert caddy_version.main([str(tmp_path / "missing")]) == 1
        assert "missing" in capsys.readouterr().err
