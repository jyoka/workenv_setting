import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "open_mention.py"
SPEC = importlib.util.spec_from_file_location("open_mention", SCRIPT_PATH)
assert SPEC and SPEC.loader
MENTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MENTION)


class FindTargetsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        (self.cwd / "a.md").write_text("a", encoding="utf-8")
        (self.cwd / "dir with space").mkdir()
        (self.cwd / "dir with space" / "b.md").write_text("b", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def find(self, prompt):
        return MENTION.find_targets(prompt, str(self.cwd))

    def test_single_file_mention_opens_file(self):
        self.assertEqual(self.find("@a.md"), [(str(self.cwd / "a.md"), None)])

    def test_line_suffix_is_passed_as_line(self):
        self.assertEqual(self.find("@a.md#L10-20"), [(str(self.cwd / "a.md"), "10")])

    def test_quoted_path_with_spaces_and_folder(self):
        targets = self.find('@"dir with space/b.md" @"dir with space/"')
        self.assertEqual([p for p, _ in targets], [str(self.cwd / "dir with space" / "b.md"), str(self.cwd / "dir with space")])

    def test_mention_with_text_is_a_normal_prompt(self):
        self.assertIsNone(self.find("@a.md explain this"))

    def test_missing_path_is_a_normal_prompt(self):
        self.assertIsNone(self.find("@a.md @missing.md"))

    def test_plain_or_empty_prompt_is_a_normal_prompt(self):
        self.assertIsNone(self.find("hello"))
        self.assertIsNone(self.find("   "))

    def test_bare_paths_accept_plain_paths_like_codex_inserts(self):
        targets = MENTION.find_targets('a.md "dir with space/b.md"', str(self.cwd), bare_paths=True)
        self.assertEqual([p for p, _ in targets], [str(self.cwd / "a.md"), str(self.cwd / "dir with space" / "b.md")])

    def test_bare_paths_still_pass_normal_prompts_through(self):
        self.assertIsNone(MENTION.find_targets("fix a.md please", str(self.cwd), bare_paths=True))
        self.assertIsNone(MENTION.find_targets("hello", str(self.cwd), bare_paths=True))

    def test_cli_mode_exit_code_tells_pi_whether_it_opened(self):
        no_match = subprocess.run([sys.executable, str(SCRIPT_PATH), "--prompt", "hello", "--cwd", str(self.cwd)], capture_output=True, text=True)
        self.assertEqual((no_match.returncode, no_match.stdout), (1, ""))


if __name__ == "__main__":
    unittest.main()
