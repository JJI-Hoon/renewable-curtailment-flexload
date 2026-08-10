"""상대성능 지수가 기상 요인을 실제로 상쇄하는지 검증."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.relative_performance import relative_index, zero_output_days  # noqa: E402


def _fixture() -> pd.DataFrame:
    """날씨는 날마다 크게 흔들리지만 발전소별 실력은 고정된 합성 데이터.

    good  = 선단 평균의 1.2배, base = 1.0배, bad = 0.8배로 고정.
    날씨 계수는 0.2~1.0까지 요동치게 만들어, 정규화가 없으면
    절대 발전량 비교가 무의미해지도록 한다.
    """
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    weather = [0.2 + 0.8 * (i % 5) / 4 for i in range(len(dates))]
    skill = {"good": 1.2, "base": 1.0, "bad": 0.8}

    rows = []
    for plant, mult in skill.items():
        for d, w in zip(dates, weather):
            rows.append(
                {
                    "plant": plant,
                    "date": d,
                    "capacity_mw": 10.0,
                    "generation_mwh": 10.0 * 24 * 0.5 * w * mult,
                }
            )
    return pd.DataFrame(rows)


def test_index_recovers_fixed_skill_despite_weather_swings():
    result = relative_index(_fixture()).set_index("plant")["relative_index"]

    # 선단 평균이 1.0이므로 각 발전소 지수는 실력 배수 × 100 이어야 한다
    assert result["good"] == 120
    assert result["base"] == 100
    assert result["bad"] == 80


def test_short_history_plants_are_dropped():
    df = _fixture()
    newcomer = df[df["plant"] == "base"].head(5).assign(plant="newcomer")
    result = relative_index(pd.concat([df, newcomer]), min_days=30)

    assert "newcomer" not in set(result["plant"])


def test_zero_output_days_counts_outages():
    df = _fixture()
    df.loc[(df["plant"] == "bad") & (df["date"] < "2024-01-08"), "generation_mwh"] = 0.0

    counts = zero_output_days(df).set_index("plant")
    assert counts.loc["bad", "zero_days"] == 7
    assert counts.loc["good", "zero_days"] == 0


if __name__ == "__main__":
    test_index_recovers_fixed_skill_despite_weather_swings()
    test_short_history_plants_are_dropped()
    test_zero_output_days_counts_outages()
    print("all tests passed")
