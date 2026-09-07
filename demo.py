"""Reproducible offline demo: no model, network, secrets or Redis required."""

import argparse
import json
from pathlib import Path
from sales_tools import BASE_DIR, DEFAULT_CSV, SalesData


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "outputs")
    parser.add_argument("--no-chart", action="store_true")
    args = parser.parse_args()
    try:
        data = SalesData(args.csv)
        result = {"data_kind": "bundled synthetic sample" if args.csv.resolve() == DEFAULT_CSV else "user supplied",
                  "sales_total": data.query("sales"), "profit_total": data.query("profit"),
                  "highest_profit_month": data.query("profit", "month", rank="highest"),
                  "product_a_quantity": data.query("quantity", product="a"), "profit_trend": data.trend()}
        if not args.no_chart:
            result["chart"] = str(data.plot("line", "profit", args.output_dir))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ValueError as exc:
        parser.exit(1, f"数据错误：{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
