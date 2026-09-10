import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import bump_porkbun

PAYLOAD = {"tag_name": "v0.4.0"}

BAKE = """variable "REGISTRY" { default = "docker.io" }

variable "CADDY_VERSION" { default = "" }
variable "CADDY_PORKBUN_VERSION" { default = "v0.3.1" }

target "image" {
  args = { CADDY_PORKBUN_VERSION = CADDY_PORKBUN_VERSION }
}
"""


class TestParseRelease:
    def test_keeps_the_tag_with_its_v_prefix(self):
        assert bump_porkbun.parse_release(PAYLOAD) == "v0.4.0"

    @pytest.mark.parametrize("tag", ["0.4.0", "v0.4", "v0.4.0-rc1", "", "main"])
    def test_rejects_unexpected_tags(self, tag):
        with pytest.raises(bump_porkbun.ApiError, match="unexpected release tag"):
            bump_porkbun.parse_release({"tag_name": tag})

    def test_rejects_a_non_object_payload(self):
        with pytest.raises(bump_porkbun.ApiError, match="unexpected release tag"):
            bump_porkbun.parse_release([PAYLOAD])


class TestFetchLatestRelease:
    def test_sends_the_api_headers_and_parses_the_release(self, monkeypatch):
        seen = {}

        def fake_urlopen(request, timeout):
            seen["request"] = request
            return io.BytesIO(json.dumps(PAYLOAD).encode())

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert bump_porkbun.fetch_latest_release() == "v0.4.0"
        request = seen["request"]
        assert request.full_url == bump_porkbun.RELEASES_URL
        assert request.get_method() == "GET"
        assert request.get_header("Accept") == "application/vnd.github+json"
        assert not request.has_header("Authorization")

    def test_uses_the_token_when_given(self, monkeypatch):
        seen = {}

        def fake_urlopen(request, timeout):
            seen["request"] = request
            return io.BytesIO(json.dumps(PAYLOAD).encode())

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        bump_porkbun.fetch_latest_release("ghp_x")
        assert seen["request"].get_header("Authorization") == "Bearer ghp_x"

    def test_http_error_includes_status_and_body(self, monkeypatch):
        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(b"rate limited"))

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(bump_porkbun.ApiError, match="HTTP 403: rate limited"):
            bump_porkbun.fetch_latest_release()

    def test_connection_error_is_reported(self, monkeypatch):
        def fake_urlopen(request, timeout):
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(bump_porkbun.ApiError, match="connection refused"):
            bump_porkbun.fetch_latest_release()


class TestBakeVariables:
    def test_reads_a_default(self):
        assert bump_porkbun.read_variable(BAKE, "CADDY_PORKBUN_VERSION") == "v0.3.1"
        assert bump_porkbun.read_variable(BAKE, "CADDY_VERSION") == ""

    def test_replaces_only_the_default_and_keeps_the_layout(self):
        text = bump_porkbun.set_variable(BAKE, "CADDY_PORKBUN_VERSION", "v0.4.0")
        assert 'variable "CADDY_PORKBUN_VERSION" { default = "v0.4.0" }' in text
        assert text.replace('"v0.4.0"', '"v0.3.1"') == BAKE

    def test_does_not_match_a_variable_with_the_same_prefix(self):
        with pytest.raises(bump_porkbun.BakeError, match="found 0"):
            bump_porkbun.read_variable(BAKE, "CADDY")

    def test_refuses_an_ambiguous_variable(self):
        with pytest.raises(bump_porkbun.BakeError, match="found 2"):
            bump_porkbun.set_variable(BAKE + BAKE, "CADDY_PORKBUN_VERSION", "v1.0.0")

    def test_parses_the_repository_bake_file(self):
        text = (Path(__file__).parents[2] / "docker-bake.hcl").read_text()
        assert bump_porkbun.TAG.match(bump_porkbun.read_variable(text, bump_porkbun.VARIABLE))


class TestBump:
    def test_rewrites_the_version(self, tmp_path):
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        assert bump_porkbun.bump(bake_file, "v0.4.0") == "v0.3.1"
        text = bake_file.read_text()
        assert bump_porkbun.read_variable(text, "CADDY_PORKBUN_VERSION") == "v0.4.0"
        assert text.count("\n") == BAKE.count("\n")

    def test_leaves_a_current_file_untouched(self, tmp_path):
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        before = bake_file.stat().st_mtime_ns
        assert bump_porkbun.bump(bake_file, "v0.3.1") is None
        assert bake_file.read_text() == BAKE
        assert bake_file.stat().st_mtime_ns == before


class TestMain:
    def test_prints_the_new_version_on_stdout(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(bump_porkbun, "fetch_latest_release", lambda token: "v0.4.0")
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        assert bump_porkbun.main([str(bake_file)]) == 0
        out, err = capsys.readouterr()
        assert out == "v0.4.0\n"
        assert "porkbun v0.3.1 -> v0.4.0" in err

    def test_prints_nothing_when_current(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(bump_porkbun, "fetch_latest_release", lambda token: "v0.3.1")
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        assert bump_porkbun.main([str(bake_file)]) == 0
        out, err = capsys.readouterr()
        assert out == ""
        assert "already at porkbun v0.3.1" in err

    def test_passes_the_token_from_the_environment(self, monkeypatch, tmp_path):
        seen = {}

        def fetch(token):
            seen["token"] = token
            return "v0.4.0"

        monkeypatch.setenv("GITHUB_TOKEN", "ghs_y")
        monkeypatch.setattr(bump_porkbun, "fetch_latest_release", fetch)
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        bump_porkbun.main([str(bake_file)])
        assert seen["token"] == "ghs_y"

    def test_api_failure_exits_1_without_touching_the_file(self, monkeypatch, tmp_path, capsys):
        def fail(token):
            raise bump_porkbun.ApiError("HTTP 500")

        monkeypatch.setattr(bump_porkbun, "fetch_latest_release", fail)
        bake_file = tmp_path / "docker-bake.hcl"
        bake_file.write_text(BAKE)
        assert bump_porkbun.main([str(bake_file)]) == 1
        assert bake_file.read_text() == BAKE
        assert "HTTP 500" in capsys.readouterr().err

    def test_missing_bake_file_exits_1(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(bump_porkbun, "fetch_latest_release", lambda token: "v0.4.0")
        assert bump_porkbun.main([str(tmp_path / "missing.hcl")]) == 1
        assert "missing.hcl" in capsys.readouterr().err
