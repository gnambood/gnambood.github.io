"""Regression tests for explicit custom-question vehicle conflicts."""
import unittest
from api.vehicle_context import vehicle_context_conflict

PAIRS = {
    ("ford", "f 150"),
    ("ford", "transit connect"),
    ("toyota", "camry"),
}

class VehicleContextTests(unittest.TestCase):
    def check(self, question, make="ford", model="transit connect", year=2021):
        return vehicle_context_conflict(question, make, model, year, PAIRS)

    def test_different_model_and_year(self):
        message = self.check("I'm considering a used 2004 Ford F-150. Is it reliable?")
        self.assertIn("2021 ford transit connect", message.lower())
        self.assertIn("2004 ford f 150", message.lower())

    def test_same_model_different_year(self):
        self.assertIsNotNone(self.check("How reliable is a 2015 Ford Transit Connect?"))

    def test_matching_identity(self):
        self.assertIsNone(self.check("How reliable is a 2021 Ford Transit Connect?"))

    def test_matching_f150(self):
        self.assertIsNone(self.check("Is the 2004 Ford F-150 reliable?", "ford", "f-150", 2004))

    def test_no_explicit_identity(self):
        self.assertIsNone(self.check("What maintenance problems do owners report?"))

    def test_model_without_make_not_assumed(self):
        self.assertIsNone(self.check("Would an F-150 be better for towing?"))

    def test_other_manufacturer(self):
        self.assertIsNotNone(self.check("What do 2020 Toyota Camry owners report?"))

    def test_comparison_not_treated_as_single_target(self):
        self.assertIsNone(self.check("Compare 2021 Ford Transit Connect with 2004 Ford F-150."))

if __name__ == "__main__":
    unittest.main()
