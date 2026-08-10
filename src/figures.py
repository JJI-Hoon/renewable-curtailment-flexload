"""data/ 의 집계 CSV로부터 figures/ 의 그림 4장을 재생성한다.

python src/figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import MultipleLocator  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "figures"

INK, MUTE, GRID = "#1a1a2e", "#8a8f98", "#e6e8eb"
RED, BLUE, GREEN = "#c0362c", "#1f6feb", "#2e7d52"

KOREAN_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "C:/Windows/Fonts/malgun.ttf",
]


def use_korean_font() -> None:
    for path in KOREAN_FONT_CANDIDATES:
        if Path(path).exists():
            fm.fontManager.addfont(path)
            plt.rcParams["font.family"] = fm.FontProperties(fname=path).get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False


def style(ax, axis: str = "y") -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.grid(axis=axis, color=GRID, lw=0.9)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTE, labelsize=10)


def save(fig, name: str) -> None:
    OUT.mkdir(exist_ok=True)
    fig.tight_layout(pad=0.6)
    fig.savefig(OUT / name, dpi=170, facecolor="white")
    plt.close(fig)
    print("wrote", name)


def fig_curtailment_by_genco() -> None:
    df = pd.read_csv(DATA / "curtailment_by_genco.csv")
    fig, ax = plt.subplots(figsize=(8.6, 2.55))
    fig.patch.set_facecolor("white")

    colors = [RED if i == 0 else "#9aa4b2" for i in range(len(df))]
    bars = ax.bar(df["genco"], df["curtailment_events"], color=colors, width=0.58)
    for bar, value in zip(bars, df["curtailment_events"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2, value + 11, str(value),
            ha="center", va="bottom", fontsize=11, color=INK, fontweight="bold",
        )

    total = int(df["curtailment_events"].sum())
    ax.set_ylim(0, df["curtailment_events"].max() * 1.23)
    ax.set_ylabel("출력제어 건수", fontsize=10.5, color=INK)
    ax.set_title(
        f"발전5사 신재생 출력제어 건수 (2년 누계 {total}건)",
        fontsize=12.5, fontweight="bold", color=INK, pad=12,
    )
    style(ax)
    save(fig, "fig1_curtailment_by_genco.png")


def fig_honam_trend() -> None:
    df = pd.read_csv(DATA / "honam_curtailment_trend.csv")
    fig, ax = plt.subplots(figsize=(8.6, 2.25))
    fig.patch.set_facecolor("white")

    labels = [f"{y}년" for y in df["year"]]
    ax.bar(labels, df["curtailed_mwh"], color=[MUTE, RED], width=0.42)
    ax.set_yscale("log")
    ax.set_ylim(df["curtailed_mwh"].min() * 0.25, df["curtailed_mwh"].max() * 7)

    for i, row in df.iterrows():
        ax.text(
            i, row["curtailed_mwh"] * 2.2,
            f"{row['curtailed_mwh']:,} MWh ({row['events']}회)",
            ha="center", va="bottom", fontsize=11,
            color=RED if i else INK, fontweight="bold" if i else "normal",
        )

    growth = df["curtailed_mwh"].iloc[-1] / df["curtailed_mwh"].iloc[0]
    ax.annotate(
        f"약 {round(growth, -2):,.0f}배", xy=(0.5, 0.70), xycoords="axes fraction",
        ha="center", fontsize=11.5, color=RED, fontweight="bold",
    )
    ax.set_ylabel("출력제어량 (MWh, 로그축)", fontsize=10.5, color=INK)
    ax.set_title("호남권 출력제어량 — 육지 확산 가속", fontsize=12.5,
                 fontweight="bold", color=INK, pad=12)
    style(ax)
    save(fig, "fig2_honam_trend.png")


def fig_relative_performance() -> None:
    df = pd.read_csv(DATA / "plant_relative_performance.csv").sort_values("relative_index")
    fig, ax = plt.subplots(figsize=(9.6, 3.15))
    fig.patch.set_facecolor("white")

    colors = [RED if v < 90 else (BLUE if v < 105 else GREEN) for v in df["relative_index"]]
    ax.barh(df["plant"], df["relative_index"], color=colors, height=0.68)
    for i, value in enumerate(df["relative_index"]):
        ax.text(value + 2, i, str(value), va="center", fontsize=10, color=INK)

    ax.axvline(100, color=MUTE, ls="--", lw=1.2)
    ax.set_xlim(0, df["relative_index"].max() * 1.2)
    ax.xaxis.set_major_locator(MultipleLocator(20))
    ax.set_xlabel("상대성능 지수 (같은 날 선단 평균 = 100)", fontsize=10.5, color=INK)
    ax.set_title("자사 태양광 13개소 상대성능 — 제주권 편중 열위",
                 fontsize=12.5, fontweight="bold", color=INK, pad=12)
    style(ax, "x")
    ax.tick_params(labelsize=10)
    save(fig, "fig3_relative_performance.png")


def fig_headroom() -> None:
    df = pd.read_csv(DATA / "curtailment_headroom.csv")
    fig, ax = plt.subplots(figsize=(8.6, 2.55))
    fig.patch.set_facecolor("white")

    labels = [
        f"{row.curtailment_share_pct}%  (연 {row.annual_hours}시간)"
        for row in df.itertuples()
    ]
    colors = [RED if abs(s - 0.5) < 1e-9 else MUTE for s in df["curtailment_share_pct"]]
    bars = ax.bar(labels, df["new_load_gw"], color=colors, width=0.46)
    for bar, value in zip(bars, df["new_load_gw"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2, value + 5, f"{value} GW",
            ha="center", va="bottom", fontsize=11, color=INK, fontweight="bold",
        )

    ax.set_ylim(0, df["new_load_gw"].max() * 1.35)
    ax.set_ylabel("수용 가능 신규 부하 (GW)", fontsize=10.5, color=INK)
    ax.set_xlabel("연간 감축 약정 비율", fontsize=10.5, color=INK)
    ax.set_title("연 0.5% 양보로 열리는 계통 여유 (美 Duke대 연구)",
                 fontsize=12.5, fontweight="bold", color=INK, pad=12)
    style(ax)
    save(fig, "fig4_headroom.png")


def main() -> None:
    use_korean_font()
    fig_curtailment_by_genco()
    fig_honam_trend()
    fig_relative_performance()
    fig_headroom()


if __name__ == "__main__":
    main()
