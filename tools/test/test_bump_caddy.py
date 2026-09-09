import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import bump_caddy

ALPINE = "sha256:" + "1" * 64
BUILDER = "sha256:" + "2" * 64
UPSTREAM = bump_caddy.Upstream("2.12.0", ALPINE, BUILDER, "v0.4.0")


def tag(name, digest):
    return {"name": name, "digest": digest}


PAGE_1 = {
    "next": "https://hub.docker.com/v2/repositories/library/caddy/tags?page=2",
    "results": [
        tag("alpine", ALPINE),
        tag("2.12.0-alpine", ALPINE),
        tag("2.12-alpine", ALPINE),
        tag("2.12.1-builder-alpine", "sha256:" + "9" * 64),
        tag("2.12.0-builder-alpine", BUILDER),
    ],
}
PAGE_2 = {
    "next": None,
    "results": [
        tag("2.9.10-alpine", "sha256:" + "3" * 64),
        tag("2.9.10-builder-alpine", "sha256:" + "4" * 64),
        tag("2.12.0-windowsservercore-ltsc2022", "sha256:" + "5" * 64),
    ],
}
PORKBUN = {"tag_name": "v0.4.0"}

BAKE = """variable "REGISTRY" { default = "docker.io" }

variable "CADDY_VERSION" { default = "2.11.4" }
variable "CADDY_DIGEST"         { default = "sha256:old-alpine" }
variable "CADDY_BUILDER_DIGEST" { default = "sha256:old-builder" }
variable "CADDY_PORKBUN_VERSION" { default = "v0.3.1" }

target "image" {
  args = { CADDY_VERSION = CADDY_VERSION }
}
"""


class TestLatestCaddyImage:
    def test_picks_the_newest_version_that_has_both_images(self):
        assert bump_caddy.latest_caddy_image(iter([PAGE_1, PAGE_2])) == ("2.12.0", ALPINE, BUILDER)

    def test_compares_versions_numerically(self):
        pages = [{"results": [tag("2.9.10-alpine", ALPINE), tag("2.9.10-builder-alpine", BUILDER)]}, PAGE_2]
        pages[1] = {
            "results": [tag("2.10.0-alpine", "sha256:" + "a" * 64), tag("2.10.0-builder-alpine", "sha256:" + "b" * 64)]
        }
        version, _, _ = bump_caddy.latest_caddy_image(iter(pages))
        assert version == "2.10.0"

    def test_ignores_tags_without_a_digest(self):
        pages = [{"results": [tag("2.12.0-alpine", ""), tag("2.12.0-builder-alpine", BUILDER), *PAGE_2["results"]]}]
        version, _, _ = bump_caddy.latest_caddy_image(iter(pages))
        assert version == "2.9.10"

    def test_fails_without_a_complete_version(self):
        with pytest.raises(bump_caddy.ApiError, match="no caddy version"):
            bump_caddy.latest_caddy_image(iter([{"results": [tag("2.12.0-alpine", ALPINE), tag("alpine", ALPINE)]}]))


class TestLatestPorkbunRelease:
    def test_keeps_the_tag_with_its_v_prefix(self):
        assert bump_caddy.latest_porkbun_release(PORKBUN) == "v0.4.0"

    @pytest.mark.parametrize("tag_name", ["0.4.0", "v0.4", "v0.4.0-rc1", "", "main"])
    def test_rejects_unexpected_tags(self, tag_name):
        with pytest.raises(bump_caddy.ApiError, match="unexpected caddy-dns/porkbun release tag"):
            bump_caddy.latest_porkbun_release({"tag_name": tag_name})

    def test_rejects_a_non_object_payload(self):
        with pytest.raises(bump_caddy.ApiError, match="unexpected"):
            bump_caddy.latest_porkbun_release([PORKBUN])


class TestFetchUpstream:
    @staticmethod
    def fake_urlopen(seen):
        responses = {
            bump_caddy.CADDY_TAGS_URL: PAGE_1,
            PAGE_1["next"]: PAGE_2,
            bump_caddy.PORKBUN_RELEASES_URL: PORKBUN,
        }

        def urlopen(request, timeout):
            seen.append(request)
            return io.BytesIO(json.dumps(responses[request.full_url]).encode())

        return urlopen

    def test_follows_the_hub_pages_and_reads_the_release(self, monkeypatch):
        seen = []
        monkeypatch.setattr(urllib.request, "urlopen", self.fake_urlopen(seen))
        assert bump_caddy.fetch_upstream() == UPSTREAM
        assert [request.full_url for request in seen] == [
            bump_caddy.CADDY_TAGS_URL,
            PAGE_1["next"],
            bump_caddy.PORKBUN_RELEASES_URL,
        ]
        github = seen[-1]
        assert github.get_header("Accept") == "application/vnd.github+json"
        assert not github.has_header("Authorization")

    def test_sends_the_token_only_to_github(self, monkeypatch):
        seen = []
        monkeypatch.setattr(urllib.request, "urlopen", self.fake_urlopen(seen))
        bump_caddy.fetch_upstream("ghp_x")
        assert [request.get_header("Authorization") for request in seen] == [None, None, "Bearer ghp_x"]

    def test_http_error_includes_status_and_body(self, monkeypatch):
        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 429, "Too Many", {}, io.BytesIO(b"rate limited"))

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(bump_caddy.ApiError, match="HTTP 429: rate limited"):
            bump_caddy.fetch_upstream()

    def test_connection_error_is_reported(self, monkeypatch):
        def fake_urlopen(request, timeout):
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(bump_caddy.ApiError, match="connection refused"):
            bump_caddy.fetch_upstream()


class TestBakeVariables:
    def test_reads_a_default(self):
        assert bump_caddy.read_variable(BAKE, "CADDY_VERSION") == "2.11.4"
        assert bump_caddy.read_variable(BAKE, "CADDY_BUILDER_DIGEST") == "sha256:old-builder"

    def test_replaces_only_the_default_and_keeps_the_layout(self):
        text = bump_caddy.set_variable(BAKE, "CADDY_DIGEST", "sha256:new")
        assert 'variable "CADDY_DIGEST"         { default = "sha256:new" }' in text
        assert text.replace('"sha256:new"', '"sha256:old-alpine"') == BAKE

    def test_does_not_match_a_variable_with_the_same_prefix(self):
        with pytest.raises(bump_caddy.BakeError, match="found 0"):
            bump_caddy.read_variable(BAKE, "CADDY")

    def test_refuses_an_ambiguous_variable(self):
        with pytest.raises(bump_caddy.BakeError, match="found 2"):
            bump_caddy.set_variable(BAKE + BAKE, "CADDY_VERSION", "1")

    def test_parses_the_repository_bake_file(self):
        text = (Path(__file__).parents[2] / "docker-bake.hcl").read_text()
        assert bump_caddy.IMAGE_TAG.match(bump_caddy.read_variable(text, "CADDY_VERSION") + "-alpine")
        assert bump_caddy.RELEASE_TAG.match(bump_caddy.read_variable(text, "CADDY_PORKBUN_VERSION"))
        for name in ("CADDY_DIGEST", "CADDY_BUILDER_DIGEST"):
            assert bump_caddy.DIGEST.match(bump_caddy.read_variable(text, name))


class TestBump:
    def test_rewrites_all_four_variables(self, tmp_path):
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        assert bump_caddy.bump(bake_file, UPSTREAM) == "caddy 2.11.4 -> 2.12.0, porkbun v0.3.1 -> v0.4.0"
        text = bake_file.read_text()
        assert {
            name: bump_caddy.read_variable(text, name) for name in UPSTREAM.bake_variables()
        } == UPSTREAM.bake_variables()
        assert text.count("\n") == BAKE.count("\n")

    def test_describes_a_digest_only_rebuild(self, tmp_path):
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        upstream = bump_caddy.Upstream("2.11.4", ALPINE, "sha256:old-builder", "v0.3.1")
        assert bump_caddy.bump(bake_file, upstream) == "caddy 2.11.4 image digests"

    def test_leaves_a_current_file_untouched(self, tmp_path):
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        before = bake_file.stat().st_mtime_ns
        current = bump_caddy.Upstream("2.11.4", "sha256:old-alpine", "sha256:old-builder", "v0.3.1")
        assert bump_caddy.bump(bake_file, current) == ""
        assert bake_file.read_text() == BAKE
        assert bake_file.stat().st_mtime_ns == before


class TestMain:
    def test_prints_the_changes_on_stdout(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(bump_caddy, "fetch_upstream", lambda token: UPSTREAM)
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        assert bump_caddy.main([str(bake_file)]) == 0
        out, err = capsys.readouterr()
        assert out == "caddy 2.11.4 -> 2.12.0, porkbun v0.3.1 -> v0.4.0\n"
        assert "docker-bake.hcl: caddy 2.11.4 -> 2.12.0" in err

    def test_prints_nothing_when_current(self, monkeypatch, tmp_path, capsys):
        current = bump_caddy.Upstream("2.11.4", "sha256:old-alpine", "sha256:old-builder", "v0.3.1")
        monkeypatch.setattr(bump_caddy, "fetch_upstream", lambda token: current)
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        assert bump_caddy.main([str(bake_file)]) == 0
        out, err = capsys.readouterr()
        assert out == ""
        assert "already at caddy 2.11.4, porkbun v0.3.1" in err

    def test_passes_the_token_from_the_environment(self, monkeypatch, tmp_path):
        seen = {}

        def fetch(token):
            seen["token"] = token
            return UPSTREAM

        monkeypatch.setenv("GITHUB_TOKEN", "ghs_y")
        monkeypatch.setattr(bump_caddy, "fetch_upstream", fetch)
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        bump_caddy.main([str(bake_file)])
        assert seen["token"] == "ghs_y"

    def test_api_failure_exits_1_without_touching_the_file(self, monkeypatch, tmp_path, capsys):
        def fail(token):
            raise bump_caddy.ApiError("HTTP 500")

        monkeypatch.setattr(bump_caddy, "fetch_upstream", fail)
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        assert bump_caddy.main([str(bake_file)]) == 1
        assert bake_file.read_text() == BAKE
        assert "HTTP 500" in capsys.readouterr().err

    def test_missing_bake_file_exits_1(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(bump_caddy, "fetch_upstream", lambda token: UPSTREAM)
        assert bump_caddy.main([str(tmp_path / "missing.hcl")]) == 1
        assert "missing.hcl" in capsys.readouterr().err
