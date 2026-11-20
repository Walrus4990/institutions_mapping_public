"""Client path, last step (rulebook 11.7): sends what a client's session added to the mapping to the repository, as one
pull request: the list of answers that were not in the mapping (11.6) and the session's decisions file (9.6), both to
input/, and the LOCAL IDs the session's run issued, added to coding/registries/local_ids.csv. The maintainer merges
it. The client needs no GitHub account.

The key is a GitHub access key of the maintainer's, limited to this repository.
It is kept in a file in the person's own user folder, outside the repository folder, and is never printed or written
to the log.
"""

import base64
import io
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
from .core.ledger import read_decision_file
from .core.personal_data import personal_data
from .pipeline import CODING, INPUT, REGISTRIES

GITHUB_REPO = "Walrus4990/institutions_mapping_public"
API = "https://api.github.com"
KEY_FILE = Path.home() / ".institution_mapping" / "github_key.txt"
LIST_NAME = re.compile(r"unmapped_institutions_(\d{4}-\d{2}-\d{2})_([A-Za-z0-9_-]+)\.xlsx")
LIST_COLUMNS = ["raw institution", "country", "learners"]
KEY_FORM = re.compile(r"[A-Za-z0-9_]{20,255}")
MAX_ROWS = 50_000
REGISTER = "coding/registries/local_ids.csv"


class GitHub:
    """The few calls to the GitHub API that sending a list needs, made with the key."""

    def __init__(self, key, repo=GITHUB_REPO):
        self.key, self.repo = key, repo

    def headers(self, json_body):
        """The headers of a call; a call that sends data declares it as JSON (GitHub refuses it otherwise)."""
        h = {
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "institution-mapping-submit",
        }
        return h | ({"Content-Type": "application/json"} if json_body else {})

    def request(self, method, path, body=None):
        """(HTTP status, answer as JSON) of one call; Stop if GitHub cannot be reached."""
        req = urllib.request.Request(
            f"{API}/repos/{self.repo}{path}",
            data=None if body is None else json.dumps(body).encode("utf-8"),
            method=method,
            headers=self.headers(body is not None),
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


def decisions_file(list_path):
    """The session's decisions file that goes with a list: input/decisions_<date>_<file>.csv of this copy."""
    m = LIST_NAME.fullmatch(Path(list_path).name)
    return INPUT / f"decisions_{m.group(1)}_{m.group(2)}.csv"


def check_decisions(path, log):
    """Rule 11.7: the session's decisions are in the ledger's form, each with a target and a rationale, and hold no
    personal data. None if the session recorded none."""
    if not path.exists():
        log.info("no decisions file (%s): only the list is sent", path.name)
        return None
    columns = list(pd.read_csv(CODING / "decisions.csv", nrows=0).columns)
    try:
        d = read_decision_file(path, columns)
    except AssertionError as e:
        raise cs.Stop(f"{e}: record the decisions with tools/add_decisions.py --to") from e
    bad = [i + 2 for i, r in d.iterrows() if not (r.raw_institution and r.target and r.rationale_type)]
    if bad:
        raise cs.Stop(f"rows {bad[:10]} of {path.name} lack an answer, a target or a rationale")
    patterns = json.loads((CODING / "coding_rules.json").read_text(encoding="utf-8"))["personal_data"]
    personal = [i + 2 for i, a in zip(d.index, d.raw_institution) if personal_data(a, patterns)]
    if personal:
        raise cs.Stop(f"rows {personal[:10]} of {path.name} are personal data: delete them, then send")
    log.info("decisions checked: %d in %s", len(d), path.name)
    return d


def new_local_ids(run_dir, log):
    """The rows of the LOCAL register that the session's run added (rule 11.7): in its register, not in this copy's."""
    base = pd.read_csv(REGISTRIES / "local_ids.csv", dtype=str, keep_default_na=False)
    if run_dir is None:
        return base.iloc[0:0]
    reg = Path(run_dir) / "work" / "coding" / "registries" / "local_ids.csv"
    if not reg.exists():
        raise cs.Stop(f"{reg} does not exist: give the folder the mapping was run into (--run)")
    run = pd.read_csv(reg, dtype=str, keep_default_na=False)[list(base.columns)]
    new = run[~run.local_id.isin(base.local_id)]
    log.info("new LOCAL IDs of the session's run: %d", len(new))
    return new


def as_lines(rows):
    """Register rows as CSV lines, in the register's format."""
    return rows.to_csv(header=False, index=False, lineterminator="\n")


def published_register(gh, base, new, log):
    """The published register as text, and its file's sha. Stops IF the session issued LOCAL IDs AND the published
    register changed since this copy was downloaded: the IDs would then clash (rule 11.7)."""
    answer = call(gh, "GET", f"/contents/{REGISTER}?ref={base}", "reading the published LOCAL register")
    text = base64.b64decode(answer["content"]).decode("utf-8")
    if len(new):
        published = set(pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False).local_id)
        mine = set(pd.read_csv(REGISTRIES / "local_ids.csv", dtype=str, keep_default_na=False).local_id)
        if published != mine:
            raise cs.Stop(
                "the published mapping has new LOCAL IDs since this copy was downloaded, so the new IDs of this "
                "session could clash: download the mapping again, run it again with the same list and decisions "
                "file, code the sheet again, then send"
            )
        log.info("the published LOCAL register is the one this session started from")
    return text, answer["sha"]


def pr_text(t, d, new, note=""):
    """The pull request's description: counts only, no answer text, and the session's note to the maintainer."""
    countries = t.groupby("country").size().sort_values(ascending=False)
    shown = ", ".join(f"{c or 'no country'} {n}" for c, n in countries.head(15).items())
    return (
        f"From a client's session (rulebook 11.7): {len(t)} answers that the mapping did not know, "
        f"{t.learners.astype(int).sum()} rows of the client's sheet. Countries: {shown}"
        + (", …" if len(countries) > 15 else "")
        + f".\n\nDecisions recorded in the session: {0 if d is None else len(d)}. New LOCAL IDs: {len(new)}."
        + "\n\nMerging adds the list and the decisions file to `input/` and the LOCAL IDs to the register. Before the "
        + "next release, `python -m institution_mapping take-in` moves the decisions into `coding/decisions.csv` "
        + "(rulebook 9.6)."
        + (f"\n\nNote from the session: {note}" if note else "")
    )


def put(gh, path, what, content, branch, sha=None):
    """Add or replace one file on the branch."""
    body = {"message": what, "content": base64.b64encode(content).decode("ascii"), "branch": branch}
    if sha:
        body["sha"] = sha
    call(gh, "PUT", f"/contents/{urllib.parse.quote(path)}", what.lower(), body)


def send(gh, pkg, log, check_only=False, note=""):
    """Branch, files, pull request (or, with check_only, every check without sending). Returns the pull request's
    web address."""
    repo = call(gh, "GET", "", "checking the key")
    base = repo["default_branch"]
    if repo.get("permissions", {}).get("push") is False:
        raise cs.Stop("the key may read the repository but not send to it: ask the maintainer of the mapping")
    path, t, d, new = pkg
    status, _ = gh.request("GET", f"/contents/{urllib.parse.quote(f'input/{path.name}')}?ref={base}")
    if status == 200:
        raise cs.Stop("a list with this name is in the repository already: it was sent before")
    register, sha = published_register(gh, base, new, log)
    if check_only:
        log.info("the key works for %s; nothing was sent", gh.repo)
        return ""
    branch = new_branch(gh, base, path.stem)
    put(gh, f"input/{path.name}", f"Client list {path.name}", path.read_bytes(), branch)
    if d is not None:
        dpath = decisions_file(path)
        put(gh, f"input/{dpath.name}", f"Client decisions {dpath.name}", dpath.read_bytes(), branch)
    if len(new):
        text = register if register.endswith("\n") else register + "\n"
        put(gh, REGISTER, f"LOCAL IDs of {path.stem}", (text + as_lines(new)).encode("utf-8"), branch, sha)
    pr = call(
        gh,
        "POST",
        "/pulls",
        "opening the pull request",
        {"title": f"Client list {path.name}", "head": branch, "base": base, "body": pr_text(t, d, new, note)},
    )
    return pr["html_url"]


def submit(list_file, run_dir=None, key_file=KEY_FILE, repo=GITHUB_REPO, check_only=False, github=None, note=""):
    """Check the list, the session's decisions and new LOCAL IDs (and the key) and, unless check_only, send them.
    Adds to the coding log beside the list. Returns 0, or 1 if something stopped it (see the log)."""
    path = Path(list_file).resolve()
    m = LIST_NAME.fullmatch(path.name)
    log_file = cs.log_path(path.parent, m.group(2) if m else path.stem)
    log, counter = cs.open_log(log_file, mode="a")
    status = 0
    try:
        log.info("submit: %s | %s", path.name, "checks only" if check_only else "checks and sending")
        t = check_list(path, log)
        d = check_decisions(decisions_file(path), log)
        if d is not None and run_dir is None:
            raise cs.Stop("the session recorded decisions: give the folder the mapping was run into (--run OUT_DIR)")
        new = new_local_ids(run_dir, log)
        gh = github or GitHub(read_key(key_file), repo)
        url = send(gh, (path, t, d, new), log, check_only, note)
        if url:
            log.info("sent: the pull request is %s", url)
        log.info("done")
    except cs.Stop as e:
        log.error("%s", e)
        status = 1
    finally:
        cs.close_log(log)
    print(f"{'stopped' if status else 'done'}: {counter.n['ERROR']} errors. Log: {log_file}")
    return status
