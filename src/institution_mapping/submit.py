"""Client path, last step (rulebook 11.7): sends the list of answers not in the mapping (11.6) to the repository, as a
pull request that adds it to input/. The maintainer merges it. The client needs no GitHub account.

The key is a GitHub access key of the maintainer's, limited to this repository (README, "Setting up the submit key").
It is kept in a file in the person's own user folder, outside the repository folder, and is never printed or written
to the log.
"""

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from . import code_sheet as cs
from .core.personal_data import personal_data
from .pipeline import CODING

GITHUB_REPO = "Walrus4990/institutions_mapping_public"
API = "https://api.github.com"
KEY_FILE = Path.home() / ".institution_mapping" / "github_key.txt"
LIST_NAME = re.compile(r"unmapped_institutions_(\d{4}-\d{2}-\d{2})_([A-Za-z0-9_-]+)\.xlsx")
LIST_COLUMNS = ["raw institution", "country", "learners"]
KEY_FORM = re.compile(r"[A-Za-z0-9_]{20,255}")
MAX_ROWS = 50_000


class GitHub:
    """The few calls to the GitHub API that sending a list needs, made with the key."""

    def __init__(self, key, repo=GITHUB_REPO):
        self.key, self.repo = key, repo

    def request(self, method, path, body=None):
        """(HTTP status, answer as JSON) of one call; Stop if GitHub cannot be reached."""
        req = urllib.request.Request(
            f"{API}/repos/{self.repo}{path}",
            data=None if body is None else json.dumps(body).encode("utf-8"),
            method=method,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "institution-mapping-submit",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw or b"null")
            except ValueError:
                return e.code, None
        except urllib.error.URLError as e:
            raise cs.Stop(
                f"GitHub cannot be reached ({e.reason}): check the internet connection, then send the list again"
            ) from e


def call(gh, method, path, what, body=None, ok=(200, 201)):
    """One call that must succeed; otherwise Stop with what went wrong, in words the person can act on."""
    status, answer = gh.request(method, path, body)
    if status in ok:
        return answer
    if status == 401:
        raise cs.Stop(
            "GitHub refused the key: it is wrong or has expired. Ask the maintainer of the mapping for a new key"
        )
    if status == 403:
        raise cs.Stop(f"the key may not do this ({what}): ask the maintainer of the mapping to check the key")
    if status == 404:
        raise cs.Stop(
            f"the repository {gh.repo} was not found with this key ({what}): the key has no access to it, or the "
            "repository has moved. Ask the maintainer of the mapping"
        )
    message = (answer or {}).get("message", "") if isinstance(answer, dict) else ""
    raise cs.Stop(f"GitHub answered {status} while {what}: {message}")


def check_list(path, log):
    """Rulebook 11.7: only a list written by the coding step, unchanged in form, is sent."""
    if not path.exists():
        raise cs.Stop(f"the list {path} does not exist")
    if not LIST_NAME.fullmatch(path.name):
        raise cs.Stop(
            "only a list written by the coding step can be sent: its name is unmapped_institutions_<date>_<file>.xlsx"
        )
    try:
        t = pd.read_excel(path, dtype=str, keep_default_na=False)
    except Exception as e:  # damaged or not a workbook
        raise cs.Stop(f"the list cannot be read ({type(e).__name__}): run the coding step again") from e
    if t.columns.tolist() != LIST_COLUMNS:
        raise cs.Stop(f"the list's columns are {t.columns.tolist()}, not {LIST_COLUMNS}: run the coding step again")
    if not 0 < len(t) <= MAX_ROWS:
        raise cs.Stop(f"the list has {len(t)} rows; a list has 1 to {MAX_ROWS}")
    bad = (
        (t["raw institution"].str.strip() == "")
        | ~t.country.str.fullmatch(r"[A-Z]{2}|")
        | ~t.learners.str.fullmatch(r"[1-9][0-9]*")
    )
    if bad.any():
        rows = [i + 2 for i in t.index[bad]][:10]
        raise cs.Stop(f"rows {rows} of the list are not in the list's form: run the coding step again")
    patterns = json.loads((CODING / "coding_rules.json").read_text(encoding="utf-8"))["personal_data"]
    personal = [i + 2 for i, a in zip(t.index, t["raw institution"]) if personal_data(a, patterns)]
    if personal:
        raise cs.Stop(f"rows {personal[:10]} of the list are personal data: delete them from the list, then send it")
    log.info(
        "list checked: %d answers, %d rows of the sheet, %d countries",
        len(t),
        t.learners.astype(int).sum(),
        t.country.nunique(),
    )
    return t


def read_key(key_file):
    """The saved key, or Stop saying how to save it."""
    key_file = Path(key_file)
    if not key_file.exists():
        raise cs.Stop(
            f"no key is saved on this computer yet ({key_file}). The key comes from the maintainer of the mapping as a "
            "small text file: save it with 'python -m institution_mapping save-key <that file>'"
        )
    key = key_file.read_text(encoding="utf-8").strip()
    if not KEY_FORM.fullmatch(key):
        raise cs.Stop(f"the saved key ({key_file}) is not in the form of a GitHub key: save the key again")
    return key


def save_key(source=None, key_file=KEY_FILE, repo=GITHUB_REPO, github=None):
    """Save the key once: from the maintainer's file, or from standard input (a pasted key). Then check that it works.
    Prints what happened, never the key. Returns 0, or 1 if nothing was saved."""
    try:
        text = Path(source).read_text(encoding="utf-8") if source else sys.stdin.read()
    except OSError as e:
        print(f"stopped: the key file cannot be read ({e.strerror})")
        return 1
    key = text.strip()
    if not KEY_FORM.fullmatch(key):
        print("stopped: this is not a GitHub key (letters, digits and '_' only, 20 or more): nothing was saved")
        return 1
    key_file = Path(key_file)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(key + "\n", encoding="utf-8")
    if os.name == "posix":
        key_file.chmod(0o600)
    print(f"key saved in {key_file}")
    try:
        call(github or GitHub(key, repo), "GET", "", "checking the key")
        print(f"the key works for {repo}")
    except cs.Stop as e:
        print(f"warning: the key was saved, but {e}")
    return 0


def new_branch(gh, base, stem):
    """A new branch for the list, from the default branch: client-list/<list name>, numbered if it exists."""
    sha = call(gh, "GET", f"/git/ref/heads/{base}", "reading the main branch")["object"]["sha"]
    for n in range(1, 21):
        name = f"client-list/{stem}" + (f"-{n}" if n > 1 else "")
        status, _ = gh.request("POST", "/git/refs", {"ref": f"refs/heads/{name}", "sha": sha})
        if status == 201:
            return name
        if status != 422:  # 422: the branch exists already
            call(gh, "POST", "/git/refs", "creating a branch", {"ref": f"refs/heads/{name}", "sha": sha})
    raise cs.Stop("20 branches for this list exist already: ask the maintainer of the mapping")


def pr_text(t):
    """The pull request's description: counts only, no answer text."""
    countries = t.groupby("country").size().sort_values(ascending=False)
    shown = ", ".join(f"{c or 'no country'} {n}" for c, n in countries.head(15).items())
    return (
        f"A list from the client path (rulebook 11.7): {len(t)} answers that the mapping does not know yet, "
        f"{t.learners.astype(int).sum()} rows of the client's sheet. Countries: {shown}"
        + (", …" if len(countries) > 15 else "")
        + ".\n\nMerging adds the list to `input/`; the next run codes its answers (rulebook 1.4)."
    )


def send(gh, path, t, log):
    """Branch, file, pull request. Returns the pull request's web address."""
    repo = call(gh, "GET", "", "checking the key")
    base = repo["default_branch"]
    if repo.get("permissions", {}).get("push") is False:
        raise cs.Stop("the key may read the repository but not send to it: ask the maintainer of the mapping")
    target = f"input/{path.name}"
    quoted = urllib.parse.quote(target)
    status, _ = gh.request("GET", f"/contents/{quoted}?ref={base}")
    if status == 200:
        raise cs.Stop("a list with this name is in the repository already: it was sent before")
    branch = new_branch(gh, base, path.stem)
    content = base64.b64encode(path.read_bytes()).decode("ascii")
    call(
        gh,
        "PUT",
        f"/contents/{quoted}",
        "adding the list",
        {"message": f"Client list {path.name}", "content": content, "branch": branch},
    )
    pr = call(
        gh,
        "POST",
        "/pulls",
        "opening the pull request",
        {"title": f"Client list {path.name}", "head": branch, "base": base, "body": pr_text(t)},
    )
    return pr["html_url"]


def submit(list_file, key_file=KEY_FILE, repo=GITHUB_REPO, check_only=False, github=None):
    """Check the list (and the key) and, unless check_only, send it. Adds to the coding log beside the list.
    Returns 0, or 1 if something stopped it (see the log)."""
    path = Path(list_file).resolve()
    m = LIST_NAME.fullmatch(path.name)
    log_file = cs.log_path(path.parent, m.group(2) if m else path.stem)
    log, counter = cs.open_log(log_file, mode="a")
    status = 0
    try:
        log.info("submit: %s | %s", path.name, "checks only" if check_only else "checks and sending")
        t = check_list(path, log)
        gh = github or GitHub(read_key(key_file), repo)
        if check_only:
            call(gh, "GET", "", "checking the key")
            log.info("the key works for %s; nothing was sent", gh.repo)
        else:
            url = send(gh, path, t, log)
            log.info("sent: the pull request is %s", url)
        log.info("done")
    except cs.Stop as e:
        log.error("%s", e)
        status = 1
    finally:
        cs.close_log(log)
    print(f"{'stopped' if status else 'done'}: {counter.n['ERROR']} errors. Log: {log_file}")
    return status
