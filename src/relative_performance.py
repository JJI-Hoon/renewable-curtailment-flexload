"""발전소별 상대성능 지수 산출.

절대 발전량 비교는 설비용량과 그날의 날씨가 뒤섞여 의미가 없다.
같은 날 선단 평균 이용률을 100으로 두고 정규화하면 기상·계통 요인이 상쇄되고
발전소 고유의 성능 차이만 남는다.

입력 CSV 컬럼: plant, date, generation_mwh, capacity_mw
"""

from __future__ import annotations

import pandas as pd

FLEET_BASE = 100.0


def daily_capacity_factor(df: pd.DataFrame) -> pd.DataFrame:
    """일별 이용률(0~1)을 컬럼으로 추가한다."""
    out = df.copy()
    out["capacity_factor"] = out["generation_mwh"] / (out["capacity_mw"] * 24.0)
    return out


def relative_index(df: pd.DataFrame, min_days: int = 30) -> pd.DataFrame:
    """발전소별 상대성능 지수(선단 평균=100)를 반환한다.

    min_days 미만으로 관측된 발전소는 표본이 부족해 제외한다.
    """
    cf = daily_capacity_factor(df)

    # 같은 날 선단 평균으로 정규화 — 전국 기상·계통 요인이 여기서 상쇄된다
    fleet_mean = cf.groupby("date")["capacity_factor"].transform("mean")
    cf = cf[fleet_mean > 0].copy()
    cf["relative"] = cf["capacity_factor"] / fleet_mean[fleet_mean > 0] * FLEET_BASE

    # 결측일·정기점검이 평균을 끌어내리므로 중앙값을 쓴다
    agg = cf.groupby("plant")["relative"].agg(["median", "count"])
    agg = agg[agg["count"] >= min_days]

    return (
        agg.rename(columns={"median": "relative_index", "count": "observed_days"})
        .assign(relative_index=lambda d: d["relative_index"].round(0).astype(int))
        .sort_values("relative_index")
        .reset_index()
    )


def zero_output_days(df: pd.DataFrame) -> pd.DataFrame:
    """발전량이 0인 날의 수 — 설비 고유 요인을 찾는 출발점."""
    zero = df.assign(is_zero=df["generation_mwh"] <= 0)
    return (
        zero.groupby("plant")["is_zero"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "zero_days", "count": "total_days"})
        .assign(zero_ratio=lambda d: (d["zero_days"] / d["total_days"]).round(3))
        .sort_values("zero_days", ascending=False)
        .reset_index()
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/generation.csv")
    raw = pd.read_csv(src, parse_dates=["date"])
    print(relative_index(raw).to_string(index=False))
    print()
    print(zero_output_days(raw).head(10).to_string(index=False))
