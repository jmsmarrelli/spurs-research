from pathlib import Path
import os, json

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".cache/matplotlib")
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Rectangle, Circle
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd
from .common import ROOT

BLACK = "#15191D"
SILVER = "#79858C"
TEAL = "#147D92"
ORANGE = "#BB4A26"
LIGHT = "#DCE3E6"
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "text.color": BLACK,
        "axes.labelcolor": BLACK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.edgecolor": LIGHT,
        "xtick.color": SILVER,
        "ytick.color": BLACK,
        "axes.titlesize": 15,
        "axes.titleweight": "bold",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "svg.fonttype": "none",
    }
)


def save(fig, name, caption):
    fig.text(0.045, 0.025, caption, fontsize=9, color=SILVER)
    fig.savefig(
        ROOT / f"figures/{name}.png",
        dpi=180,
        bbox_inches="tight",
        metadata={"Software": None},
    )
    fig.savefig(
        ROOT / f"figures/{name}.svg",
        bbox_inches="tight",
        metadata={"Creator": None, "Date": None, "Description": caption},
    )
    plt.close(fig)


def court(ax):
    for p in [
        Rectangle((-25, -5.25), 50, 47, fill=False),
        Rectangle((-8, -5.25), 16, 19, fill=False),
        Circle((0, 0), 0.75, fill=False),
        Arc((0, 13.75), 12, 12, theta1=0, theta2=180),
        Arc((0, 0), 47.5, 47.5, theta1=22, theta2=158),
    ]:
        p.set_edgecolor(SILVER)
        p.set_linewidth(0.7)
        ax.add_patch(p)
    ax.plot([-22, -22], [-5.25, 8.9], color=SILVER, lw=0.7)
    ax.plot([22, 22], [-5.25, 8.9], color=SILVER, lw=0.7)
    ax.set_xlim(-25, 25)
    ax.set_ylim(-5.25, 35)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["bottom"].set_visible(False)


def run():
    raw = pd.read_csv(ROOT / "results/rim_raw.csv")
    est = pd.read_csv(ROOT / "results/rim_estimates.csv")
    q = est[est.controls]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    fig.subplots_adjust(left=0.11, right=0.95, bottom=0.24, top=0.80, wspace=0.42)
    for ax, col, title in [
        (axes[0], "rim_share", "Share of opponent shots at the rim"),
        (axes[1], "rim_fg_pct", "Accuracy on those rim attempts"),
    ]:
        ax.bar(
            ["Wembanyama off", "Wembanyama on"],
            raw[col],
            color=[SILVER, BLACK],
            width=0.55,
        )
        ax.set_ylim(0, 0.8 if col == "rim_fg_pct" else 0.36)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_title(title, loc="left", pad=18, fontsize=13)
        for i, v in enumerate(raw[col]):
            ax.text(i, v + 0.015, f"{v:.1%}", ha="center", fontweight="bold")
    save(
        fig,
        "rim_raw",
        "2025-26: 63 games with opponent attempts in both states. Raw rates; field goal attempts only.",
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.subplots_adjust(left=0.30, right=0.96, bottom=0.23, top=0.8)
    names = ["Rim share", "Rim finishing"]
    colors = [BLACK, TEAL]
    for i, name in enumerate(names):
        r = q[q.outcome.eq(name)].iloc[0]
        v = r.estimate * 100
        lo = r.lower * 100
        hi = r.upper * 100
        ax.errorbar(
            v,
            1 - i,
            xerr=[[v - lo], [hi - v]],
            fmt="o",
            color=colors[i],
            capsize=5,
            ms=8,
        )
        ax.text(v, 1 - i + 0.15, f"{v:+.1f} pp", ha="center", fontweight="bold")
    ax.set_yticks([1, 0], ["Rim-attempt share", "Rim field goal percentage"])
    ax.axvline(0, color=LIGHT)
    ax.set_ylim(-0.45, 1.5)
    ax.set_xlabel("Wembanyama on minus off, within games (percentage points)")
    ax.set_title("The clearer association is where shots are taken", loc="left", pad=18)
    save(
        fig,
        "rim_adjusted",
        "Adjusted linear models with game fixed effects. Bars: 95% game-cluster bootstrap intervals.",
    )
    s = pd.read_csv(ROOT / "results/rim_sensitivity.csv")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    fig.subplots_adjust(left=0.37, right=0.96, bottom=0.24, top=0.81)
    for i, r in s.iterrows():
        v = r.estimate * 100
        ax.errorbar(
            v,
            i,
            xerr=[[v - r.lower * 100], [r.upper * 100 - v]],
            fmt="o",
            capsize=4,
            color=TEAL,
        )
        ax.text(v, i + 0.20, f"{int(r.games)} games", ha="center", va="top", fontsize=9)
    ax.set_yticks(
        range(len(s)),
        ["Before January", "January onward", "Competitive-score sensitivity"],
    )
    ax.set_ylim(2.45, -0.45)
    ax.axvline(0, color=LIGHT)
    ax.set_xlim(-14, 2)
    ax.set_xlabel("Adjusted rim-share difference (percentage points)")
    ax.set_title(
        "Does the result depend on one part of the season?", loc="left", pad=18
    )
    save(
        fig,
        "rim_sensitivity",
        "Sensitivity removes margins above 15 points and the final two minutes of Q4 or overtime.",
    )
    g = pd.read_csv(ROOT / "results/guard_groups.csv").sort_values("minutes")
    labels = g.group.str.replace(" + ", " / ", regex=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.subplots_adjust(left=0.28, right=0.95, bottom=0.2, top=0.84)
    bars = ax.barh(
        labels,
        g.minutes,
        color=[ORANGE if x == "Fox + Castle + Harper" else SILVER for x in g.group],
    )
    for bar, (_, r) in zip(bars, g.iterrows()):
        ax.text(
            bar.get_width() + 12,
            bar.get_y() + bar.get_height() / 2,
            f"{r.minutes:.0f} min · {int(r.attempts):,} FGA",
            va="center",
            fontsize=10,
        )
    ax.set_xlim(0, g.minutes.max() * 1.35)
    ax.set_xlabel("Reconstructed regular-season minutes")
    ax.set_title("Three guards together is still a small sample", loc="left", pad=18)
    save(
        fig,
        "guard_exposure",
        "81 games, with unresolved periods excluded. Group labels describe which guards are on the floor.",
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.subplots_adjust(left=0.28, right=0.95, bottom=0.22, top=0.84)
    for i, (_, r) in enumerate(g.iterrows()):
        color = ORANGE if r.group == "Fox + Castle + Harper" else BLACK
        ax.errorbar(
            r.rim_share,
            i,
            xerr=[[r.rim_share - r.rim_boot_low], [r.rim_boot_high - r.rim_share]],
            fmt="o",
            color=color,
            capsize=4,
        )
    ax.set_yticks(range(len(g)), labels)
    ax.set_xlim(0, 0.8)
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xlabel("Share of Spurs field goal attempts in the restricted area")
    ax.set_title(
        "A high rim share does not settle the rotation question", loc="left", pad=18
    )
    save(
        fig,
        "guard_rim_intervals",
        "95% game-cluster bootstrap intervals. The three-guard estimate is based on 46 attempts.",
    )
    edges = pd.read_csv(ROOT / "results/guard_assist_connections.csv")
    receivers = [
        "Victor Wembanyama",
        "Julian Champagnie",
        "Devin Vassell",
        "Luke Kornet",
        "Keldon Johnson",
        "Harrison Barnes",
    ]
    mat = (
        edges.pivot(index="assist_name", columns="receiver", values="assisted_makes")
        .fillna(0)
        .reindex(index=["Fox", "Castle", "Harper"], columns=receivers, fill_value=0)
    )
    fig, ax = plt.subplots(figsize=(10, 4.7))
    fig.subplots_adjust(left=0.10, right=0.96, bottom=0.31, top=0.79)
    ax.imshow(mat, cmap="Blues", aspect="auto")
    ax.set_yticks(range(3), mat.index)
    ax.set_xticks(
        range(6),
        ["Wembanyama", "Champagnie", "Vassell", "Kornet", "Johnson", "Barnes"],
        rotation=25,
        ha="right",
    )
    for i in range(3):
        for j in range(6):
            ax.text(
                j,
                i,
                str(int(mat.iloc[i, j])),
                ha="center",
                va="center",
                color=(
                    "white" if mat.iloc[i, j] > mat.to_numpy().max() * 0.55 else BLACK
                ),
                fontweight="bold",
            )
    ax.set_title("Whose made baskets did each guard assist?", loc="left", pad=18)
    save(
        fig,
        "guard_assists",
        "Assisted makes in retained periods, not passes, potential assists, or assists per shared minute.",
    )
    p = pd.read_csv(ROOT / "results/playoff_zone_profiles.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    fig.subplots_adjust(left=0.19, right=0.96, bottom=0.26, top=0.82, wspace=0.30)
    order = ["Restricted area", "Other paint", "Midrange", "Three-pointer"]
    for i, (metric, title) in enumerate(
        [
            ("attempt_weight", "Opponent-matched shot mix"),
            ("ppa", "Points per attempt in each zone"),
        ]
    ):
        x = p.pivot(index="zone", columns="phase", values=metric).loc[order]
        y = np.arange(4)
        axes[i].hlines(y, x["Matched regular season"], x["Playoffs"], color=LIGHT, lw=4)
        axes[i].scatter(
            x["Matched regular season"],
            y,
            color=SILVER,
            s=65,
            label="Matched regular season",
        )
        axes[i].scatter(x["Playoffs"], y, color=ORANGE, s=65, label="Playoffs")
        axes[i].set_yticks(y, order if i == 0 else [""] * 4)
        axes[i].invert_yaxis()
        axes[i].set_title(title, loc="left", pad=15, fontsize=13)
        if i == 0:
            axes[i].xaxis.set_major_formatter(PercentFormatter(1))
            axes[i].set_xlim(0, 0.55)
    handles, labels_ = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels_,
        loc="lower left",
        bbox_to_anchor=(0.19, 0.085),
        ncol=2,
        frameon=False,
        fontsize=10,
    )
    save(
        fig,
        "playoff_profile",
        "Wembanyama: MIN, NYK and OKC only. Regular-season opponents weighted to playoff attempt shares.",
    )
    v = pd.read_csv(ROOT / "results/playoff_decomposition.csv")
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.subplots_adjust(left=0.31, right=0.96, bottom=0.24, top=0.82)
    for i, r in v.iterrows():
        x = r.estimate * 100
        ax.errorbar(
            x,
            2 - i,
            xerr=[[x - r.lower * 100], [r.upper * 100 - x]],
            fmt="o",
            color=[TEAL, ORANGE, BLACK][i],
            capsize=5,
            ms=8,
        )
        ax.text(x, 2 - i + 0.19, f"{x:+.1f}", ha="center", fontweight="bold")
    ax.set_yticks([2, 1, 0], v.component)
    ax.axvline(0, color=LIGHT)
    ax.set_ylim(-0.5, 2.55)
    ax.set_xlabel("Playoffs minus matched regular season: points per 100 FGA")
    ax.set_title("The scoring loss is mostly within locations", loc="left", pad=18)
    save(
        fig,
        "playoff_components",
        "95% bootstrap intervals. Only nine regular-season comparison games; opponent weights held fixed.",
    )
    d = pd.read_csv(ROOT / "data/playoff_shots.csv.gz")
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.8))
    fig.subplots_adjust(left=0.04, right=0.96, bottom=0.15, top=0.84, wspace=0.12)
    for ax, (phase, frame) in zip(axes, d.groupby("phase", sort=True)):
        color = SILVER if phase == "Matched regular season" else ORANGE
        ax.scatter(
            frame.LOC_X / 10,
            frame.LOC_Y / 10,
            s=16,
            color=color,
            alpha=0.45,
            linewidths=0,
        )
        court(ax)
        ax.set_title(f"{phase}\n{len(frame)} attempts", fontsize=13, loc="left", pad=10)
    save(
        fig,
        "playoff_shotmap",
        "Shot locations from the NBA feed. Court is a reference diagram; dots overlap and are not density estimates.",
    )
    return 9


if __name__ == "__main__":
    print(run())
