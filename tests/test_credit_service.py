import os
import unittest

from src.services.credit_service import CreditService


class CreditServiceTestCase(unittest.TestCase):
    def test_rate_helpers_fall_back_when_env_values_are_blank(self):
        previous_dollar = os.environ.get("CREDITS_PER_DOLLAR")
        previous_tokens = os.environ.get("CREDITS_PER_1K_TOKENS")
        try:
            os.environ["CREDITS_PER_DOLLAR"] = ""
            os.environ["CREDITS_PER_1K_TOKENS"] = "not-a-number"

            service = CreditService()

            self.assertEqual(service._get_credits_per_dollar(), 100)
            self.assertEqual(service._get_credits_per_1k_tokens(), 10)
        finally:
            if previous_dollar is None:
                os.environ.pop("CREDITS_PER_DOLLAR", None)
            else:
                os.environ["CREDITS_PER_DOLLAR"] = previous_dollar
            if previous_tokens is None:
                os.environ.pop("CREDITS_PER_1K_TOKENS", None)
            else:
                os.environ["CREDITS_PER_1K_TOKENS"] = previous_tokens


if __name__ == "__main__":
    unittest.main()
