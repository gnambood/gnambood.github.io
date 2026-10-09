"""Regression coverage for legacy Edmunds whitespace characters.

Run from the auto-market-assistant directory:
    python -m unittest discover -s tests -p 'test_review_whitespace.py'
"""
import unittest

import pandas as pd

from pipelines.transform_reviews import clean_reviews


class ReviewWhitespaceTests(unittest.TestCase):
    def test_nel_and_nbsp_are_normalized_in_title_and_text(self):
        raw = pd.DataFrame({
            "manufacturer": ["ford", "toyota"],
            "source_file": ["Scraped_Car_Review_ford.csv", "Scrapped_Car_Reviews_Toyota.csv"],
            "Vehicle_Title": ["2015 Ford Escape SUV", "2018 Toyota Camry Sedan"],
            "Review_Title": [
                "Great\u0085\u00a0 ride",
                "Very\u00a0 comfortable",
            ],
            "Review": [
                "This\u0085 vehicle\u00a0 drives very well, and the ride is comfortable.",
                "The\u00a0 interior\u0085 is spacious and comfortable for everyday use.",
            ],
            "Rating": [4.5, 4.0],
            "Review_Date": ["Jan 01, 2020", "Jan 02, 2020"],
        })
        cleaned = clean_reviews(raw)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(cleaned.iloc[0]["review_title"], "Great ride")
        self.assertEqual(
            cleaned.iloc[0]["review_text"],
            "This vehicle drives very well, and the ride is comfortable.",
        )
        self.assertEqual(cleaned.iloc[1]["review_title"], "Very comfortable")
        self.assertEqual(
            cleaned.iloc[1]["review_text"],
            "The interior is spacious and comfortable for everyday use.",
        )
        for field in ("review_title", "review_text"):
            self.assertFalse(cleaned[field].str.contains("\u0085|\u00a0", regex=True).any())


if __name__ == "__main__":
    unittest.main()
