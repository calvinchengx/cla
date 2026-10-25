"""Controls for cla_check.py and validate_signature.py.

Each way a check exists to fail is provoked and required to fail, and each way
it must pass is required to pass. A gate that never fires looks exactly like a
project where everyone has signed.

Run:  python3 -m unittest test_cla.py
"""
import datetime
import unittest

import cla_check
import validate_signature as vs

OWNER = 1
ALICE = {"id": 10, "login": "alice", "type": "User"}
BOB = {"id": 20, "login": "bob", "type": "User"}
BOT = {"id": 99, "login": "dependabot[bot]", "type": "Bot"}
SIGNED = "github_id,github_login,full_name,icla_version,signed_on,employer\n10,alice,Alice A,1.0,2026-10-25,\n"


def commit(user, email="x@example.com"):
    return {"author": user, "commit": {"author": {"email": email}}}


class ClaCheck(unittest.TestCase):
    def run_check(self, author, commits):
        people = cla_check.people_to_check({"user": author}, commits)
        return cla_check.verdict(people, cla_check.signed_ids(SIGNED), OWNER)

    def test_signed_author_passes(self):
        self.assertEqual(self.run_check(ALICE, [commit(ALICE)])[0], [])

    def test_unsigned_author_fails(self):
        self.assertEqual(self.run_check(BOB, [commit(BOB)])[0], ["@bob (PR author)"])

    def test_unsigned_commit_author_fails_even_if_pr_author_signed(self):
        self.assertEqual(self.run_check(ALICE, [commit(ALICE), commit(BOB)])[0], ["@bob"])

    def test_commit_without_github_account_fails(self):
        missing, _ = self.run_check(ALICE, [commit(None, "ghost@example.com")])
        self.assertEqual(missing, ["<ghost@example.com> (no GitHub account)"])

    def test_bots_and_owner_pass_unsigned(self):
        owner = {"id": OWNER, "login": "calvinchengx", "type": "User"}
        self.assertEqual(self.run_check(BOT, [commit(BOT), commit(owner)])[0], [])

    def test_match_is_by_id_not_login(self):
        renamed = {"id": 10, "login": "alice-new", "type": "User"}
        impostor = {"id": 30, "login": "alice", "type": "User"}
        self.assertEqual(self.run_check(renamed, [])[0], [])
        self.assertEqual(self.run_check(impostor, [])[0], ["@alice (PR author)"])


class ValidateSignature(unittest.TestCase):
    TODAY = datetime.date(2026, 10, 25)
    BODY = vs.STATEMENT.format(v="1.0")

    def files(self, patch, additions=1, deletions=0, name=vs.CSV_PATH):
        return [{"filename": name, "additions": additions, "deletions": deletions, "patch": patch}]

    def check(self, line, author=BOB, body=BODY, existing=frozenset({10})):
        return vs.check_row(line, author, existing, "1.0", self.TODAY, body)

    def test_valid_row(self):
        self.assertEqual(self.check("20,bob,Bob Builder,1.0,2026-10-25,"), [])
        self.assertEqual(self.check("20,Bob,Bob Builder,1.0,2026-10-24,Acme Ltd"), [])

    def test_row_for_someone_else_fails(self):
        problems = self.check("10,alice,Alice A,1.0,2026-10-25,")
        self.assertTrue(any("github_id" in p for p in problems))
        self.assertTrue(any("github_login" in p for p in problems))

    def test_each_field_is_checked(self):
        cases = {
            "20,bob,bob,1.0,2026-10-25,": "full_name",
            "20,bob,Bob Builder,0.9,2026-10-25,": "icla_version",
            "20,bob,Bob Builder,1.0,2026-10-01,": "signed_on",
            "20,bob,Bob Builder,1.0,25/10/2026,": "not a YYYY-MM-DD",
            "20,bob,Bob Builder,1.0": "fields",
        }
        for line, want in cases.items():
            with self.subTest(line=line):
                self.assertTrue(any(want in p for p in self.check(line)), self.check(line))

    def test_statement_and_resigning(self):
        self.assertTrue(any("word for word" in p for p in self.check("20,bob,Bob Builder,1.0,2026-10-25,", body="ok")))
        self.assertIn("you have already signed",
                      self.check("10,alice,Alice A,1.0,2026-10-25,", author=ALICE, existing={10}))

    def test_diff_shape(self):
        self.assertEqual(vs.added_line(self.files("@@ -1 +1,2 @@\n header\n+20,bob,Bob,1.0,2026-10-25,")),
                         "20,bob,Bob,1.0,2026-10-25,")
        for files, want in [
            (self.files("", name="ICLA.md"), "changes only"),
            (self.files("+a\n+b", additions=2), "exactly one line"),
            (self.files("-x\n+y", deletions=1), "exactly one line"),
            (self.files("+a") + self.files("+b", name="README.md"), "changes only"),
        ]:
            with self.subTest(want=want), self.assertRaisesRegex(ValueError, want):
                vs.added_line(files)

    def test_version_comes_from_icla(self):
        self.assertEqual(vs.current_version(open("ICLA.md", encoding="utf-8").read()), "1.0")


if __name__ == "__main__":
    unittest.main()
