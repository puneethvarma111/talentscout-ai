import asyncio
import os
import unittest

os.environ["LLM_PROVIDER"] = "mock"

from app.copilot import agent  # noqa: E402
from app.copilot.docs import make_doc, redact_pii  # noqa: E402
from app.copilot.tools import get_session, run_tool  # noqa: E402


def collect(session, msg):
    async def go():
        return [e async for e in agent.run(session, msg)]
    return asyncio.run(go())


class CopilotTests(unittest.TestCase):
    def test_employee_cannot_see_others(self):
        s = get_session("t-emp"); s.persona = "employee"
        self.assertFalse(run_tool(s, "get_leave_balance", {"employee": "Rahul"})["ok"])
        self.assertTrue(run_tool(s, "get_leave_balance", {"employee": "me"})["ok"])

    def test_manager_scoped_to_team(self):
        s = get_session("t-mgr"); s.persona = "manager"
        self.assertTrue(run_tool(s, "get_leave_balance", {"employee": "Rahul"})["ok"])
        self.assertFalse(run_tool(s, "get_leave_balance", {"employee": "Arjun"})["ok"])

    def test_offer_letter_is_pending_and_hr_only(self):
        s = get_session("t-hr"); s.persona = "hr"
        r = run_tool(s, "draft_offer_letter", {"candidate_name": "A B", "role": "QA Engineer", "ctc_lpa": 10})
        self.assertEqual(r["approval"]["status"], "pending")
        s.persona = "manager"
        self.assertFalse(run_tool(s, "draft_offer_letter", {"candidate_name": "A", "role": "QA"})["ok"])

    def test_resume_screen_redacts_and_scores(self):
        s = get_session("t-cv"); s.persona = "hr"
        s.docs.append(make_doc("cv.txt", "Resume\nx@y.com\n6 years Python and AWS\nDocker", "resume"))
        r = run_tool(s, "screen_resume", {"must_have": ["python", "aws", "kafka"], "min_years": 5})
        self.assertIn("kafka", r["data"]["gaps"])
        self.assertNotIn("x@y.com", str(r))
        self.assertEqual(redact_pii("call +91 98765 43210"), "call [phone redacted]")

    def test_policy_not_found_does_not_guess(self):
        s = get_session("t-pol")
        r = run_tool(s, "search_hr_policy", {"question": "zzqx unicorn"})
        self.assertEqual(r["data"]["matches"], [])

    def test_mock_stream_events(self):
        s = get_session("t-stream"); s.persona = "manager"
        evs = collect(s, "Who is out on leave in the next 30 days?")
        kinds = [e["type"] for e in evs]
        for k in ("meta", "step", "artifact", "token", "done"):
            self.assertIn(k, kinds)


if __name__ == "__main__":
    unittest.main()
