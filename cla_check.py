"""Fail a pull request whose authors have not signed the ICLA.

Runs inside the composite action in action.yml, from a `pull_request_target`
workflow: the code that runs is always this repository's, at the SHA the caller
pinned, never the pull request's. It reads only PR metadata, through the API
with a read-only token, and the signature list, which is fetched live from this
repository's main branch, so signing never needs a pin bump.

Who must have signed: the PR author and every commit author. People are matched
by GitHub user id, which survives a rename. Commit authors whose email is not
linked to a GitHub account cannot be verified, so they fail too. Two kinds of
author pass without a signature: bots (`type == "Bot"`, which you installed
yourself) and the repository owner.

Stdlib only. Environment:
    GITHUB_EVENT_PATH, GITHUB_TOKEN   set by Actions
    CLA_SIGNATURES_REPO               default calvinchengx/cla
    CLA_SIGNATURES_FILE               local CSV instead of fetching (tests, dry runs)
    GITHUB_STEP_SUMMARY               optional; the result is written there too
"""

import csv
import io
import json
import os
import sys
import urllib.request

API = "https://api.github.com"
SIGN_URL = "https://github.com/{repo}/blob/main/README.md#signing"


def api_get(path, token):
    req = urllib.request.Request(API + path, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def pr_commits(repo, number, token):
    """Every commit on the PR, paginated (the endpoint caps at 250)."""
    commits, page = [], 1
    while True:
        batch = api_get(f"/repos/{repo}/pulls/{number}/commits?per_page=100&page={page}", token)
        commits += batch
        if len(batch) < 100:
            return commits
        page += 1


def fetch_signatures(repo, token):
    req = urllib.request.Request(f"{API}/repos/{repo}/contents/signatures/icla.csv?ref=main", headers={
        "Accept": "application/vnd.github.raw+json",
        "Authorization": f"Bearer {token}",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def signed_ids(csv_text):
    """GitHub user ids that have a row in icla.csv."""
    return {int(row["github_id"]) for row in csv.DictReader(io.StringIO(csv_text)) if row.get("github_id", "").strip()}


def people_to_check(pr, commits):
    """(label, user-or-None) for the PR author and each distinct commit author."""
    seen, out = set(), []
    def add(label, user):
        key = user["id"] if user else ("email", label)
        if key not in seen:
            seen.add(key)
            out.append((label, user))
    add(f"@{pr['user']['login']} (PR author)", pr["user"])
    for c in commits:
        user = c.get("author")
        label = f"@{user['login']}" if user else f"<{c['commit']['author']['email']}> (no GitHub account)"
        add(label, user)
    return out


def verdict(people, signed, owner_id):
    """Return (missing labels, passed labels)."""
    missing, passed = [], []
    for label, user in people:
        if user is None:
            missing.append(label)
        elif user.get("type") == "Bot" or user["id"] == owner_id or user["id"] in signed:
            passed.append(label)
        else:
            missing.append(label)
    return missing, passed


def main():
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8"))
    token = os.environ["GITHUB_TOKEN"]
    pr, repo = event["pull_request"], event["repository"]
    sig_repo = os.environ.get("CLA_SIGNATURES_REPO", "calvinchengx/cla")

    local = os.environ.get("CLA_SIGNATURES_FILE")
    csv_text = open(local, encoding="utf-8").read() if local else fetch_signatures(sig_repo, token)
    commits = pr_commits(repo["full_name"], pr["number"], token)
    missing, passed = verdict(people_to_check(pr, commits), signed_ids(csv_text), repo["owner"]["id"])

    lines = [f"CLA: {len(passed)} covered, {len(missing)} not covered."]
    lines += [f"  ✓ {p}" for p in passed] + [f"  ✗ {m}" for m in missing]
    if missing:
        lines.append(f"Sign the Individual Contributor License Agreement: {SIGN_URL.format(repo=sig_repo)}")
        lines.append("Then re-run this check (or push again).")
    print("\n".join(lines))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
