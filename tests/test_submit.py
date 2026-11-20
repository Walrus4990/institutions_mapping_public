"""The client path's last step (rulebook 11.7): the list is checked, then sent as a pull request; the key is never
shown. GitHub is replaced by a fake: no test reaches the network."""

import io

import pandas as pd
import pytest

from institution_mapping import submit as sm

KEY = "github_pat_" + "x" * 40


class FakeGitHub:
    """Answers like GitHub; records the calls. `answers` overrides (method, path prefix) -> (status, body)."""

    def __init__(self, answers=None, existing_branches=()):
        self.repo, self.calls, self.answers = "owner/repo", [], dict(answers or {})
        self.branches = set(existing_branches)

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        for (m, prefix), answer in self.answers.items():
            if m == method and path.startswith(prefix):
                return answer
        if method == "GET" and path == "":
            return 200, {"default_branch": "main", "permissions": {"push": True}}
        if method == "GET" and path.startswith("/git/ref/heads/"):
            return 200, {"object": {"sha": "abc"}}
        if method == "GET" and path.startswith("/contents/"):
            return 404, {"message": "Not Found"}
        if method == "POST" and path == "/git/refs":
            name = body["ref"].removeprefix("refs/heads/")
            if name in self.branches:
                return 422, {"message": "Reference already exists"}
            self.branches.add(name)
            return 201, {}
        if method == "PUT":
            return 201, {}
        if method == "POST" and path == "/pulls":
            return 201, {"html_url": "https://github.com/owner/repo/pull/7"}
        raise AssertionError((method, path))


def a_list(folder, rows=None, name="unmapped_institutions_2026-11-20_survey.xlsx"):
    rows = rows or [["Nowhere College", "KE", 2], ["nowhere institute", "", 1]]
    path = folder / name
    pd.DataFrame(rows, columns=sm.LIST_COLUMNS).to_excel(path, sheet_name="unmapped", index=False)
    return path


def log_of(folder):
    return (folder / "survey_coding_log.txt").read_text(encoding="utf-8")


def test_sends_the_list_as_a_pull_request(tmp_path):
    gh = FakeGitHub()
    assert sm.submit(a_list(tmp_path), github=gh) == 0
    methods = [(m, p.split("?")[0]) for m, p, _ in gh.calls]
    assert methods == [
        ("GET", ""),
        ("GET", "/contents/input/unmapped_institutions_2026-11-20_survey.xlsx"),
        ("GET", "/git/ref/heads/main"),
        ("POST", "/git/refs"),
        ("PUT", "/contents/input/unmapped_institutions_2026-11-20_survey.xlsx"),
        ("POST", "/pulls"),
    ]
    pr = gh.calls[-1][2]
    assert pr["head"] == "client-list/unmapped_institutions_2026-11-20_survey" and pr["base"] == "main"
    assert "2 answers" in pr["body"] and "Nowhere" not in pr["body"]  # counts only, no answer text
    assert "sent: the pull request is https://github.com/owner/repo/pull/7" in log_of(tmp_path)


def test_a_second_list_of_the_same_name_gets_a_numbered_branch(tmp_path):
    gh = FakeGitHub(existing_branches={"client-list/unmapped_institutions_2026-11-20_survey"})
    assert sm.submit(a_list(tmp_path), github=gh) == 0
    assert gh.calls[-1][2]["head"].endswith("_survey-2")


def test_check_only_sends_nothing(tmp_path):
    gh = FakeGitHub()
    assert sm.submit(a_list(tmp_path), check_only=True, github=gh) == 0
    assert [m for m, _, _ in gh.calls] == ["GET"]
    assert "nothing was sent" in log_of(tmp_path)


@pytest.mark.parametrize(
    ("answers", "error"),
    [
        ({("GET", ""): (401, {"message": "Bad credentials"})}, "wrong or has expired"),
        ({("GET", ""): (404, {"message": "Not Found"})}, "was not found with this key"),
        ({("GET", ""): (200, {"default_branch": "main", "permissions": {"push": False}})}, "not send to it"),
        ({("GET", "/contents/"): (200, {})}, "was sent before"),
        ({("POST", "/pulls"): (403, {"message": "forbidden"})}, "may not do this (opening the pull request)"),
    ],
)
def test_github_refusals_are_explained(tmp_path, answers, error):
    assert sm.submit(a_list(tmp_path), github=FakeGitHub(answers)) == 1
    log = log_of(tmp_path)
    assert "ERROR" in log and error in log, log


@pytest.mark.parametrize(
    ("rows", "name", "error"),
    [
        (None, "my_list.xlsx", "only a list written by the coding step"),
        ([["someone@example.org", "KE", 1]], None, "are personal data"),
        ([["Nowhere College", "Kenya", 1]], None, "not in the list's form"),
        ([["Nowhere College", "KE", 0]], None, "not in the list's form"),
    ],
)
def test_lists_that_are_not_sent(tmp_path, rows, name, error):
    path = a_list(tmp_path, rows, name or "unmapped_institutions_2026-11-20_survey.xlsx")
    gh = FakeGitHub()
    assert sm.submit(path, github=gh) == 1
    assert gh.calls == []
    log = (tmp_path / f"{'survey' if name is None else 'my_list'}_coding_log.txt").read_text(encoding="utf-8")
    assert error in log, log


def test_the_list_is_checked_before_the_key(tmp_path):
    assert sm.submit(a_list(tmp_path), key_file=tmp_path / "none.txt") == 1
    assert "no key is saved on this computer yet" in log_of(tmp_path)


def test_save_key_from_a_file_and_from_a_paste(tmp_path, monkeypatch, capsys):
    target = tmp_path / "home" / "key.txt"
    source = tmp_path / "from_maintainer.txt"
    source.write_text(KEY + "\n", encoding="utf-8")
    assert sm.save_key(source, target, github=FakeGitHub()) == 0
    assert target.read_text(encoding="utf-8").strip() == KEY
    assert sm.read_key(target) == KEY
    monkeypatch.setattr("sys.stdin", io.StringIO("  " + KEY + "  \n"))
    assert sm.save_key(None, target, github=FakeGitHub()) == 0
    out = capsys.readouterr().out
    assert "the key works for" in out and KEY not in out  # never printed
    monkeypatch.setattr("sys.stdin", io.StringIO("not a key"))
    assert sm.save_key(None, tmp_path / "other.txt") == 1
    assert not (tmp_path / "other.txt").exists()


def test_the_key_is_never_in_the_log(tmp_path):
    key_file = tmp_path / "key.txt"
    key_file.write_text(KEY, encoding="utf-8")
    sm.submit(a_list(tmp_path), key_file=key_file, github=FakeGitHub())
    assert KEY not in log_of(tmp_path)
