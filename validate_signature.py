"""Check a signing pull request before the maintainer merges it.

A signing PR adds exactly one row to signatures/icla.csv, for its own author,
and its description carries the signing statement. This verifies all of that
from the API and the event payload, without checking out the PR, so it is safe
under `pull_request_target`.

Stdlib only. Environment: GITHUB_EVENT_PATH, GITHUB_TOKEN.
"""

import csv
import datetime
import io
import json
import os
import pathlib
import re
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
CSV_PATH = "signatures/icla.csv"
CCLA_PATH = "signatures/ccla.csv"
FIELDS = ["github_id", "github_login", "full_name", "icla_version", "signed_on", "employer"]
STATEMENT = "I have read the Individual Contributor License Agreement version {v} and I agree to its terms."


def current_version(icla_text):
    m = re.search(r"\*\*Version (\d+\.\d+)", icla_text)
    if not m:
        raise SystemExit("ICLA.md has no '**Version X.Y' line")
    return m.group(1)


def added_line(files):
    """The single added CSV line, or raise ValueError saying what is wrong."""
    if [f["filename"] for f in files] != [CSV_PATH]:
        raise ValueError(f"a signing PR changes only {CSV_PATH}; this one changes "
                         + ", ".join(f["filename"] for f in files))
    f = files[0]
    if f.get("additions") != 1 or f.get("deletions") != 0:
        raise ValueError(f"add exactly one line and remove none (got +{f.get('additions')} -{f.get('deletions')})")
    lines = [ln[1:] for ln in f.get("patch", "").splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    if len(lines) != 1:
        raise ValueError("could not find the added line in the diff")
    return lines[0]


def ccla_companies(csv_text):
    """Employers with a CCLA on file, normalised for matching."""
    return {r["company"].strip().casefold() for r in csv.DictReader(io.StringIO(csv_text)) if r.get("company", "").strip()}


def check_row(line, author, existing_ids, version, opened_on, body, companies=frozenset()):
    """Return a list of problems with the new row; empty means it is valid."""
    rows = list(csv.reader(io.StringIO(line)))
    if len(rows) != 1 or len(rows[0]) != len(FIELDS):
        return [f"the row needs exactly {len(FIELDS)} comma-separated fields: {','.join(FIELDS)}"]
    row = dict(zip(FIELDS, (v.strip() for v in rows[0])))
    problems = []
    if row["github_id"] != str(author["id"]):
        problems.append(f"github_id is {row['github_id']!r}; yours is {author['id']}")
    if row["github_login"].lower() != author["login"].lower():
        problems.append(f"github_login is {row['github_login']!r}; yours is {author['login']!r}")
    if author["id"] in existing_ids:
        problems.append("you have already signed")
    if len(row["full_name"]) < 2 or row["full_name"].lower() == author["login"].lower():
        problems.append("full_name must be your full legal name")
    if row["icla_version"] != version:
        problems.append(f"icla_version is {row['icla_version']!r}; the current version is {version}")
    try:
        signed = datetime.date.fromisoformat(row["signed_on"])
        if abs((signed - opened_on).days) > 1:
            problems.append(f"signed_on {signed} should be today ({opened_on}, UTC)")
    except ValueError:
        problems.append(f"signed_on {row['signed_on']!r} is not a YYYY-MM-DD date")
    # A named employer is held until its CCLA is on file: the maintainer adds
    # the company to signatures/ccla.csv after receiving the signed agreement.
    if row["employer"] and row["employer"].casefold() not in companies:
        problems.append(f"employer {row['employer']!r} has no CCLA on file yet. Your employer must "
                        f"sign CCLA.md first, and the name must match {CCLA_PATH} exactly. "
                        "If you contribute in a personal capacity, leave employer empty")
    if STATEMENT.format(v=version) not in (body or ""):
        problems.append("the PR description must contain, word for word: " + STATEMENT.format(v=version))
    return problems


def api_get(path, token, raw=False):
    req = urllib.request.Request("https://api.github.com" + path, headers={
        "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8") if raw else json.load(resp)


def main():
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8"))
    token = os.environ["GITHUB_TOKEN"]
    pr, repo = event["pull_request"], event["repository"]["full_name"]
    version = current_version((HERE / "ICLA.md").read_text(encoding="utf-8"))
    files = api_get(f"/repos/{repo}/pulls/{pr['number']}/files", token)
    existing = {int(r["github_id"]) for r in csv.DictReader(io.StringIO((HERE / CSV_PATH).read_text(encoding="utf-8")))}
    try:
        line = added_line(files)
    except ValueError as e:
        problems = [str(e)]
    else:
        opened_on = datetime.datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00")).date()
        companies = ccla_companies((HERE / CCLA_PATH).read_text(encoding="utf-8"))
        problems = check_row(line, pr["user"], existing, version, opened_on, pr["body"], companies)
    if problems:
        print("signature: not valid yet")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"signature: valid ICLA v{version} signature for @{pr['user']['login']}; ready for the maintainer to merge")
    return 0


if __name__ == "__main__":
    sys.exit(main())
