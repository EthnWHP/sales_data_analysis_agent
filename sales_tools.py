"""Deterministic sales calculations, independent of any model or API key."""

import calendar
import math
import re
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = BASE_DIR / "sales.csv"
METRICS = {"sales", "profit", "quantity"}
DIMENSIONS = {"month", "region", "product"}
MONTHS = list(calendar.month_abbr)[1:]


def normalize_month(value: str) -> str:
    """Accept English month abbreviations (one year) or YYYY-MM, not both."""
    value = str(value).strip()
    for month in MONTHS:
        if value.casefold() == month.casefold():
            return month
    if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        return value
    raise ValueError("month 必须为 Jan–Dec 或 YYYY-MM。")


def month_key(value: str) -> int:
    if value in MONTHS:
        return MONTHS.index(value)
    year, month = map(int, value.split("-"))
    return year * 12 + month - 1


class SalesData:
    """Validated CSV with explicit aggregation and filter semantics."""

    def __init__(self, path: str | Path = DEFAULT_CSV):
        try:
            self.df = pd.read_csv(path, dtype={name: "str" for name in DIMENSIONS})
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
            raise ValueError("无法读取销售 CSV，请检查文件路径和格式。") from exc
        if not (METRICS | DIMENSIONS).issubset(self.df.columns):
            raise ValueError("CSV 必须包含 month, region, product, sales, profit, quantity。")
        if self.df.empty:
            raise ValueError("CSV 不能为空。")
        for name in DIMENSIONS:
            if self.df[name].isna().any():
                raise ValueError(f"{name} 不允许为空。")
            self.df[name] = self.df[name].str.strip()
            if self.df[name].eq("").any():
                raise ValueError(f"{name} 不允许为空。")
        self.df["month"] = self.df["month"].map(normalize_month)
        if self.df["month"].isin(MONTHS).any() and not self.df["month"].isin(MONTHS).all():
            raise ValueError("同一 CSV 不可混用月份缩写与 YYYY-MM。")
        for name in METRICS:
            self.df[name] = pd.to_numeric(self.df[name], errors="coerce")
            if not self.df[name].map(math.isfinite).all():
                raise ValueError(f"{name} 必须为有限数值，不允许缺失、NaN 或无穷大。")
        if (self.df["sales"] < 0).any() or (self.df["quantity"] < 0).any():
            raise ValueError("此 Demo 要求 sales、quantity 非负；profit 可以为负。")
        if self.df["quantity"].mod(1).ne(0).any():
            raise ValueError("quantity 必须是整数。")

    def query(self, metric="sales", group_by=None, operation="sum", product=None,
              month=None, region=None, rank=None):
        """Aggregate after filtering. Rank selects all tied groups, never a raw row."""
        if metric not in METRICS or group_by not in DIMENSIONS | {None}:
            raise ValueError("不支持的指标或分组。")
        if operation not in {"sum", "mean", "min", "max"}:
            raise ValueError("operation 必须为 sum、mean、min 或 max。")
        if rank not in {None, "highest", "lowest"} or (rank and not group_by):
            raise ValueError("rank 必须为 highest/lowest，且必须指定分组。")
        frame = self.df
        for field, value in {"product": product, "month": month, "region": region}.items():
            if value is not None:
                value = normalize_month(value) if field == "month" else str(value).strip()
                frame = frame[frame[field].str.casefold() == value.casefold()]
        result = {"metric": metric, "operation": operation, "group_by": group_by,
                  "matched_rows": len(frame), "results": []}
        if frame.empty:
            result["message"] = "没有匹配的数据，不能将缺失数据解释为零。"
            return result
        if group_by is None:
            result["results"] = [{"value": float(frame[metric].agg(operation))}]
            return result
        grouped = frame.groupby(group_by)[metric].agg(operation)
        if group_by == "month":
            grouped = grouped.reindex(sorted(grouped.index, key=month_key))
        if rank:
            target = grouped.max() if rank == "highest" else grouped.min()
            grouped = grouped[grouped == target]
        result["results"] = [{group_by: str(label), "value": float(value)}
                             for label, value in grouped.items()]
        return result

    def trend(self, metric="profit"):
        rows = self.query(metric=metric, group_by="month")["results"]
        changes = []
        for previous, current in zip(rows, rows[1:]):
            delta = current["value"] - previous["value"]
            changes.append({"from": previous["month"], "to": current["month"],
                            "gap_months": month_key(current["month"]) - month_key(previous["month"]),
                            "change": delta,
                            "change_percent": round(delta / previous["value"] * 100, 2)
                            if previous["value"] > 0 else None})
        return {"metric": metric, "monthly": rows, "changes": changes,
                "note": "仅比较已有月份；gap_months>1 不是连续月环比。基期<=0时不计算百分比。汇总数据不能证明变化原因。"}

    def plot(self, chart_type="line", metric="sales", output_dir=BASE_DIR / "outputs"):
        if chart_type not in {"line", "bar"} or metric not in METRICS:
            raise ValueError("chart_type 为 line/bar，metric 为 sales/profit/quantity。")
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        dimension = "month" if chart_type == "line" else "region"
        rows = self.query(metric=metric, group_by=dimension)["results"]
        figure = Figure(figsize=(9, 5), layout="constrained")
        FigureCanvasAgg(figure)
        axes = figure.subplots()
        labels, values = [r[dimension] for r in rows], [r["value"] for r in rows]
        if chart_type == "line":
            axes.plot(labels, values, marker="o", color="#2563eb", linewidth=2)
        else:
            axes.bar(labels, values, color="#2563eb")
        axes.set(title=f"{metric.capitalize()} by {dimension}", xlabel=dimension.capitalize(),
                 ylabel=metric.capitalize())
        axes.grid(axis="y", alpha=0.2)
        destination = Path(output_dir).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / f"sales_{metric}_{chart_type}.png"
        figure.savefig(path, dpi=150)
        return path


def build_tools(data_path=DEFAULT_CSV, output_dir=BASE_DIR / "outputs"):
    """Bind the same validated calculations to each agent implementation."""
    from typing import Literal
    from langchain_core.tools import tool

    data = SalesData(data_path)

    @tool
    def query_sales_data(metric: Literal["sales", "profit", "quantity"] = "sales",
                         group_by: Literal["month", "region", "product"] | None = None,
                         operation: Literal["sum", "mean", "min", "max"] = "sum",
                         product: str | None = None, month: str | None = None,
                         region: str | None = None,
                         rank: Literal["highest", "lowest"] | None = None) -> dict:
        """查询销售额sales/利润profit/销量quantity。先按产品、月份、地区精确筛选，再按group_by聚合。
        最高利润月份应使用 metric=profit, group_by=month, operation=sum, rank=highest。
        mean 是记录均值，min/max 是记录极值；并列排名全部返回。month 用 Jan–Dec 或 YYYY-MM。
        """
        try:
            return data.query(metric, group_by, operation, product, month, region, rank)
        except ValueError as exc:
            return {"error": str(exc)}

    @tool
    def plot_sales_data(chart_type: Literal["line", "bar"] = "line",
                        metric: Literal["sales", "profit", "quantity"] = "sales") -> str:
        """生成图表：line 按自然月份排序汇总；bar 按地区汇总。只写本地输出目录。"""
        return f"图表已保存：{data.plot(chart_type, metric, output_dir)}"

    @tool
    def analyze_sales_trend(metric: Literal["sales", "profit", "quantity"] = "profit") -> dict:
        """按自然月份比较指标变化。仅计算事实，不推断业务因果；缺月不补零。"""
        return data.trend(metric)

    return [query_sales_data, plot_sales_data, analyze_sales_trend]
