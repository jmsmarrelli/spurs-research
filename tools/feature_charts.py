"""Rebuild the flagship uncertainty chart: python -m tools.feature_charts."""
from pathlib import Path
import pandas as pd
from .chart_style import canvas, finish, stat, note, tidy, TEAL, MUTED, GRID

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = pd.read_csv(ROOT / "results/rim_estimates.csv")
    q = data[data.controls].set_index("outcome").loc[["Rim share", "Rim finishing"]]
    fig = canvas("02 / Rim protection", "The clearer footprint is where shots are taken",
                 "Wembanyama on minus off · 2025–26 regular season · adjusted within-game comparisons")
    ax = fig.add_axes([.265, .28, .45, .39])
    for i, (_, r) in enumerate(q.iterrows()):
        v, lo, hi = r[["estimate", "lower", "upper"]].astype(float) * 100
        color = TEAL if i == 0 else MUTED
        ax.hlines(i, lo, hi, color=color, lw=3)
        ax.scatter(v, i, color=color, s=110, zorder=3)
        ax.text(v, i-.23, f"{v:+.1f} pp", ha="center", weight="bold", color=color, fontsize=17)
        ax.text(v, i+.24, f"95% interval: {lo:+.1f} to {hi:+.1f}", ha="center", color=MUTED, fontsize=10)
    ax.axvline(0, color=GRID, lw=1.2)
    ax.set_yticks([0, 1], ["Rim-attempt share", "Accuracy at the rim"])
    ax.set_ylim(1.65, -.65)
    ax.set_xlim(-8.5, 5.5)
    ax.set_xticks([-8, -6, -4, -2, 0, 2, 4])
    ax.set_xlabel("On minus off (percentage points)", labelpad=14)
    tidy(ax)
    stat(fig, .79, .69, str(int(q.iloc[0].games)), "games with both on/off states")
    stat(fig, .79, .55, f"{int(q.iloc[0].attempts):,}", "opponent field-goal attempts")
    note(fig, .79, .43, "The basketball question", "What lets opponents reach the rim despite his presence? Start a film queue from those possessions.", width=25)
    note(fig, .79, .255, "The identification limit", "Lineups still differ. This does not isolate player credit.", width=25)
    finish(fig, ROOT / "figures/rim_adjusted",
           "Source: results/rim_estimates.csv · Rim finishing uses 1,436 rim attempts; attempt share uses all 5,726 attempts.",
           "Linear models with game fixed effects and recorded controls. Horizontal lines: 95% game-cluster bootstrap intervals.")


if __name__ == "__main__":
    main()
