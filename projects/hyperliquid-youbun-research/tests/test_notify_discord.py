import unittest

from scripts.notify_discord import build_message


class NotifyDiscordTest(unittest.TestCase):
    def test_success_message_contains_handoff_fields(self):
        message = build_message("success", "state files", "6 passed", "branch abc123", "visual review")
        self.assertIn("Status: SUCCESS", message)
        self.assertIn("branch abc123", message)
        self.assertIn("ChatGPT確認", message)

    def test_warning_includes_note(self):
        message = build_message("warning", "setup", "6 passed", "branch abc123", "next", "webhook未設定")
        self.assertIn("COMPLETED WITH NOTES", message)
        self.assertIn("webhook未設定", message)


if __name__ == "__main__":
    unittest.main()
