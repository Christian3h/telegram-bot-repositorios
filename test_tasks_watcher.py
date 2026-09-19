#!/usr/bin/env python3
import unittest
import datetime
from tasks_watcher import PrigmaTasksWatcher

class TestPrigmaTasksWatcher(unittest.TestCase):
    def setUp(self):
        self.watcher = PrigmaTasksWatcher(
            bot_token="123456:TEST_TOKEN",
            pragma_api_url="http://localhost:3000",
            api_key="test_api_key",
            working_hours_start=8,
            working_hours_end=18,
            working_days=(0, 1, 2, 3, 4), # Mon-Fri
        )

    def test_working_hours(self):
        # Mon at 10 AM -> True
        mon_10am = datetime.datetime(2026, 9, 14, 10, 0, 0)
        self.assertTrue(self.watcher.is_working_hours(mon_10am))

        # Mon at 7 AM -> False (before start)
        mon_7am = datetime.datetime(2026, 9, 14, 7, 0, 0)
        self.assertFalse(self.watcher.is_working_hours(mon_7am))

        # Mon at 19 PM -> False (after end)
        mon_19pm = datetime.datetime(2026, 9, 14, 19, 0, 0)
        self.assertFalse(self.watcher.is_working_hours(mon_19pm))

        # Sunday at 10 AM -> False (weekend)
        sun_10am = datetime.datetime(2026, 9, 20, 10, 0, 0)
        self.assertFalse(self.watcher.is_working_hours(sun_10am))

    def test_generate_keyboard(self):
        kb = self.watcher.generate_task_keyboard("task-uuid-123")
        self.assertIn("inline_keyboard", kb)
        buttons = kb["inline_keyboard"]
        self.assertEqual(len(buttons), 2)
        self.assertEqual(buttons[0][0]["callback_data"], "ts:task-uuid-123:in_progress")
        self.assertEqual(buttons[0][1]["callback_data"], "ts:task-uuid-123:in_review")
        self.assertEqual(buttons[1][0]["callback_data"], "ts:task-uuid-123:completed")
        self.assertEqual(buttons[1][1]["callback_data"], "ts:task-uuid-123:blocked")

    def test_format_task_message(self):
        sample_task = {
            "task_code": "PRIG-101",
            "title": "Optimizar caché en Supabase",
            "status": "in_progress",
            "priority": "high",
            "due_date": "2026-09-30",
            "assignee_name": "Daniel",
        }
        msg = self.watcher.format_task_message(sample_task)
        self.assertIn("PRIG-101", msg)
        self.assertIn("Optimizar caché", msg)
        self.assertIn("HIGH", msg)
        self.assertIn("Daniel", msg)

if __name__ == "__main__":
    unittest.main()
