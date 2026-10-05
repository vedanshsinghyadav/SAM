"""
Unit tests for src/sam/personality/adapter.py.
Validates context-adaptive dual-tone switching, witty hardware metrics formatting,
concise task execution formatting, modality sanitization, and protocol compliance.
"""

import unittest
from src.sam.personality.interface import IPersonalityAdapter, OutputModality, ToneMode
from src.sam.personality.adapter import PersonalityAdapter


class TestPersonalityAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = PersonalityAdapter()

    def test_implements_protocol(self):
        self.assertTrue(isinstance(self.adapter, IPersonalityAdapter))

    def test_determine_tone_mode_casual(self):
        mode = self.adapter.determine_tone_mode(decision_type="reply", has_active_task=False)
        self.assertEqual(mode, ToneMode.CASUAL)

    def test_determine_tone_mode_task(self):
        mode = self.adapter.determine_tone_mode(decision_type="tool_call", tool_name="move_file")
        self.assertEqual(mode, ToneMode.TASK)

        mode_plan = self.adapter.determine_tone_mode(decision_type="plan")
        self.assertEqual(mode_plan, ToneMode.TASK)

        mode_active = self.adapter.determine_tone_mode(decision_type="reply", has_active_task=True)
        self.assertEqual(mode_active, ToneMode.TASK)

    def test_determine_tone_mode_system_query(self):
        mode = self.adapter.determine_tone_mode(tool_name="get_system_stats")
        self.assertEqual(mode, ToneMode.SYSTEM_QUERY)

        mode2 = self.adapter.determine_tone_mode(user_intent="query_cpu_stats")
        self.assertEqual(mode2, ToneMode.SYSTEM_QUERY)

    def test_cpu_usage_personality_acceptance_criteria(self):
        """
        Verifies Acceptance Criteria line 77:
        'CPU usage query returns a response with at least mild personality, not just a raw number'
        """
        # Low load (< 25%)
        resp_low = self.adapter.format_system_metric("cpu", 15.0)
        self.assertIn("15%", resp_low)
        self.assertNotEqual(resp_low.strip(), "15%")
        self.assertNotEqual(resp_low.strip(), "15")
        self.assertTrue(any(w in resp_low.lower() for w in ("cool", "sweat", "idling", "cruising")))

        # High load (> 85%)
        resp_high = self.adapter.format_system_metric("cpu", 92.0)
        self.assertIn("92%", resp_high)
        self.assertTrue(any(w in resp_high.lower() for w in ("fans", "hard", "hot", "engaged")))

    def test_memory_and_battery_personality(self):
        resp_ram = self.adapter.format_system_metric("ram", 88.0)
        self.assertIn("88%", resp_ram)
        self.assertTrue("chrome" in resp_ram.lower() or "appetite" in resp_ram.lower())

        resp_bat = self.adapter.format_system_metric("battery", 14.0)
        self.assertIn("14%", resp_bat)
        self.assertTrue("cable" in resp_bat.lower() or "power" in resp_bat.lower())

    def test_task_response_concise_professional(self):
        """
        Verifies Acceptance Criteria line 78:
        'Task execution responses are concise and professional, not chatty'
        """
        resp = self.adapter.adapt_task_response(
            action="move_file",
            target="latest PDF",
            details="COA folder"
        )
        self.assertEqual(resp, "Moved latest PDF to COA folder.")
        # Ensure zero robotic or conversational filler
        self.assertNotIn("Certainly", resp)
        self.assertNotIn("I'd be glad to", resp)
        self.assertNotIn("Sure thing", resp)

    def test_modality_sanitization_voice_vs_text(self):
        raw_markdown = "**CPU is at 15%**, sir. Check `powershell` [YouTube](https://www.youtube.com)."

        # Text mode preserves markdown
        text_out = self.adapter.sanitize_for_modality(raw_markdown, OutputModality.TEXT)
        self.assertIn("**CPU is at 15%**", text_out)

        # Voice mode strips symbols and expands phonetics
        voice_out = self.adapter.sanitize_for_modality(raw_markdown, OutputModality.VOICE)
        self.assertNotIn("**", voice_out)
        self.assertNotIn("`", voice_out)
        self.assertNotIn("https://", voice_out)
        self.assertIn("15 percent", voice_out)
        self.assertIn("YouTube", voice_out)

    def test_system_prompt_directives(self):
        task_dir = self.adapter.get_system_prompt_directive(ToneMode.TASK)
        self.assertIn("Professional", task_dir)

        casual_dir = self.adapter.get_system_prompt_directive(ToneMode.CASUAL)
        self.assertIn("JARVIS", casual_dir)

        query_dir = self.adapter.get_system_prompt_directive(ToneMode.SYSTEM_QUERY)
        self.assertIn("Informative", query_dir)

    def test_adapt_tone_and_format_response_helpers(self):
        toned_task = self.adapter.adapt_tone("Moved file to Notes", is_task=True)
        self.assertEqual(toned_task, "Moved file to Notes.")

        toned_casual = self.adapter.adapt_tone("CPU is 18.5%", is_task=False)
        self.assertIn("silicon", toned_casual.lower())

        resp = self.adapter.format_response("  Hello  ", modality="text")
        self.assertEqual(resp, "Hello")


if __name__ == "__main__":
    unittest.main()
