import tempfile
import unittest
from pathlib import Path

import pandas as pd
from sales_tools import DEFAULT_CSV, SalesData


class SalesTests(unittest.TestCase):
    def setUp(self):
        self.data = SalesData()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def changed(self, **columns):
        frame = pd.read_csv(DEFAULT_CSV)
        for name, value in columns.items():
            frame[name] = value
        path = Path(self.temp.name) / "fixture.csv"
        frame.to_csv(path, index=False)
        return SalesData(path)

    def test_totals(self):
        for metric, expected in {"sales": 12900, "profit": 2580, "quantity": 1290}.items():
            self.assertEqual(self.data.query(metric)["results"], [{"value": expected}])

    def test_months_are_chronological_after_shuffle(self):
        frame = pd.read_csv(DEFAULT_CSV).iloc[::-1]
        path = Path(self.temp.name) / "shuffled.csv"
        frame.to_csv(path, index=False)
        self.assertEqual(SalesData(path).query("profit", "month")["results"],
                         [{"month": "Jan", "value": 740}, {"month": "Feb", "value": 760},
                          {"month": "Mar", "value": 1080}])

    def test_group_ranking_is_not_record_max(self):
        # Highest record is Jan (400), but highest monthly total is Feb (750).
        data = self.changed(profit=[400, 0, 0, 250, 250, 250, 200, 200, 200])
        self.assertEqual(data.query("profit", "month", rank="highest")["results"],
                         [{"month": "Feb", "value": 750}])

    def test_tied_groups_are_all_returned(self):
        data = self.changed(profit=[100] * 9)
        self.assertEqual(len(data.query("profit", "month", rank="highest")["results"]), 3)

    def test_combined_filters_case_insensitive(self):
        result = self.data.query("quantity", product="a", month="MAR", region="east")
        self.assertEqual(result["matched_rows"], 1)
        self.assertEqual(result["results"], [{"value": 200}])
        self.assertEqual(self.data.query("quantity", product="a")["results"], [{"value": 720}])

    def test_no_match_is_not_zero(self):
        result = self.data.query(product="not-a-product")
        self.assertEqual(result["results"], [])
        self.assertEqual(result["matched_rows"], 0)

    def test_min_max_mean(self):
        self.assertEqual(self.data.query("profit", operation="min")["results"], [{"value": 200}])
        self.assertEqual(self.data.query("profit", operation="max")["results"], [{"value": 400}])
        self.assertAlmostEqual(self.data.query("profit", operation="mean")["results"][0]["value"], 2580 / 9)

    def test_invalid_query_parameters(self):
        for kwargs in [{"metric": "password"}, {"group_by": "city"}, {"operation": "eval"},
                       {"rank": "highest"}, {"month": "13月"}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.data.query(**kwargs)

    def test_trend(self):
        rows = self.data.trend()["changes"]
        self.assertEqual([row["change"] for row in rows], [20, 320])
        self.assertEqual([row["change_percent"] for row in rows], [2.7, 42.11])

    def test_zero_base(self):
        self.assertIsNone(self.changed(profit=[0] * 9).trend()["changes"][0]["change_percent"])

    def test_year_month_and_missing_period(self):
        data = self.changed(month=["2026-03"] * 3 + ["2025-12"] * 3 + ["2026-01"] * 3)
        changes = data.trend()["changes"]
        self.assertEqual([row["gap_months"] for row in changes], [1, 2])

    def test_invalid_csv_values(self):
        for columns in [{"sales": [float("inf")] * 9}, {"quantity": [1.5] * 9},
                        {"sales": [-1] * 9}, {"region": [""] * 9}, {"profit": ["oops"] * 9},
                        {"month": ["Jan"] * 8 + ["2026-02"]}, {"month": ["wrong"] * 9}]:
            with self.subTest(columns=columns), self.assertRaises(ValueError):
                self.changed(**columns)

    def test_negative_profit_allowed(self):
        self.assertEqual(self.changed(profit=[-10] * 9).query("profit")["results"], [{"value": -90}])

    def test_missing_empty_and_bad_schema(self):
        for name, content in [("empty.csv", ""), ("schema.csv", "x,y\n1,2\n"),
                              ("header.csv", "month,region,product,sales,profit,quantity\n")]:
            path = Path(self.temp.name) / name
            path.write_text(content)
            with self.assertRaises(ValueError):
                SalesData(path)
        with self.assertRaises(ValueError):
            SalesData(Path(self.temp.name) / "missing.csv")

    def test_plot_and_invalid_chart(self):
        for kind in ["line", "bar"]:
            path = self.data.plot(kind, "profit", self.temp.name)
            self.assertTrue(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        with self.assertRaises(ValueError):
            self.data.plot("pie", output_dir=self.temp.name)


if __name__ == "__main__":
    unittest.main()
