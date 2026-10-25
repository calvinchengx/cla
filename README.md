# Contributor License Agreements

Every project under `github.com/calvinchengx` that accepts outside
contributions asks contributors to sign a CLA first. There are two:

- [ICLA.md](ICLA.md): for an individual. Everyone who contributes signs this.
- [CCLA.md](CCLA.md): for a company or other organisation that owns what its
  employees create. The employer signs this and lists who it covers; each of
  those people also signs the ICLA.

**Why a CLA, and not just the license.** You keep your copyright. The CLA gives
the maintainer the right to relicense your contribution (section 2). In return
it promises that your contribution always stays available under the license the
project had when you submitted it (section 3). It also records who granted what,
separately from git history.

**Status: DRAFT v1.0.** Not in force until a lawyer has reviewed it and this
notice is removed.

## Signing

You sign once, and it covers every project.

1. Read [ICLA.md](ICLA.md).
2. Open a pull request to this repository from your own GitHub account. It adds
   one line to [`signatures/icla.csv`](signatures/icla.csv):
   `github_id,github_login,full_name,icla_version,signed_on,employer`.
   The pull request template has the exact format, and the statement your PR
   description must contain.
3. The "Validate signature" check confirms that the line is yours and
   complete. The maintainer then merges it, and from that moment the "CLA"
   check passes on your pull requests in every project. Re-run it there, or
   push again.

The file is public: it lists your name and GitHub account, never your email.
Accounts are matched by GitHub's numeric user id, so renaming your account
doesn't undo your signature.

If you contribute as part of your job, check with your employer first. In many
countries, including the UK for civil servants (Crown copyright), your employer
owns what you write at work, and only they can grant these rights. In that case
your employer signs the CCLA.

## For projects

A project requires the CLA by running this repository's composite action from a
`pull_request_target` workflow. The usage block is at the top of
[`action.yml`](action.yml). It fails a pull request if the author, or any
commit author, has not signed. Bots and the repository owner pass without a
signature. It never checks out or runs code from the pull request.
