import json
import numpy as np
import pandas as pd
from .common import ROOT, shots, save_json, SEED


def within_game(frame, outcome, controls=True, reps=2000):
    d = frame.copy()
    eligible = d.groupby("GAME_ID").Wembanyama.nunique()
    d = d[d.GAME_ID.isin(eligible[eligible == 2].index)].copy()
    columns = ["Wembanyama"]
    if controls:
        d["margin_scaled"] = d.margin.clip(-25, 25) / 25
        d["margin_squared"] = d.margin_scaled**2
        d["period_clock"] = d.seconds / 720
        for n in [2, 3, 4, 5]:
            d[f"period_{n}"] = d.PERIOD.eq(n).astype(float)
        columns += [
            "margin_scaled",
            "margin_squared",
            "period_clock",
            "prior_rim_share",
            "period_2",
            "period_3",
            "period_4",
            "period_5",
        ]
    values = d[columns + [outcome]].astype(float)
    centered = values - values.groupby(d.GAME_ID).transform("mean")
    xx = []
    xy = []
    for _, g in centered.groupby(d.GAME_ID):
        x = g[columns].to_numpy()
        y = g[outcome].to_numpy()
        xx.append(x.T @ x)
        xy.append(x.T @ y)
    xx = np.array(xx)
    xy = np.array(xy)
    estimate = float((np.linalg.pinv(xx.sum(axis=0)) @ xy.sum(axis=0))[0])
    rng = np.random.default_rng(SEED)
    draws = []
    for _ in range(reps):
        idx = rng.integers(0, len(xx), len(xx))
        draws.append((np.linalg.pinv(xx[idx].sum(axis=0)) @ xy[idx].sum(axis=0))[0])
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return {
        "estimate": estimate,
        "lower": lo,
        "upper": hi,
        "games": d.GAME_ID.nunique(),
        "attempts": len(d),
        "controls": controls,
    }


def run():
    d = pd.read_csv(ROOT / "data/spurs_shots.csv.gz", parse_dates=["date"])
    d = d[d.opponent.eq("SAS")].copy()
    old = shots(2024)
    old["rim"] = old.SHOT_ZONE_BASIC.eq("Restricted Area").astype(int)
    prior = old.groupby("PLAYER_ID").rim.agg(["sum", "count"])
    league = old.rim.mean()
    prior["rate"] = (prior["sum"] + 100 * league) / (prior["count"] + 100)
    d["prior_rim_share"] = d.PLAYER_ID.map(prior.rate).fillna(league)
    d["rim"] = d.SHOT_ZONE_BASIC.eq("Restricted Area").astype(int)
    both = d.groupby("GAME_ID").Wembanyama.nunique()
    d = d[d.GAME_ID.isin(both[both == 2].index)].copy()
    raw = (
        d.groupby("Wembanyama")
        .agg(
            attempts=("made", "size"),
            rim_attempts=("rim", "sum"),
            rim_share=("rim", "mean"),
            field_goal_ppa=("points", "mean"),
        )
        .reset_index()
    )
    rim = (
        d[d.rim.eq(1)]
        .groupby("Wembanyama")
        .made.agg(rim_fgm="sum", rim_fga="size", rim_fg_pct="mean")
        .reset_index()
    )
    raw = raw.merge(rim, on="Wembanyama")
    raw.to_csv(ROOT / "results/rim_raw.csv", index=False)
    estimates = []
    for label, frame, outcome in [
        ("Rim share", d, "rim"),
        ("Rim finishing", d[d.rim.eq(1)], "made"),
        ("FG points per attempt", d, "points"),
    ]:
        for controls in [False, True]:
            estimates.append(
                {"outcome": label, **within_game(frame, outcome, controls)}
            )
    pd.DataFrame(estimates).to_csv(ROOT / "results/rim_estimates.csv", index=False)
    sensitivity = []
    for label, frame in [
        ("Before January", d[d.date < "2026-01-01"]),
        ("January onward", d[d.date >= "2026-01-01"]),
        (
            "Margin <=15; exclude final 2m Q4/OT",
            d[d.margin.abs().le(15) & ~(d.PERIOD.ge(4) & d.seconds.le(120))],
        ),
    ]:
        sensitivity.append({"sample": label, **within_game(frame, "rim", True, 1000)})
    pd.DataFrame(sensitivity).to_csv(ROOT / "results/rim_sensitivity.csv", index=False)
    game = (
        d.groupby(["GAME_ID", "Wembanyama"])
        .agg(attempts=("made", "size"), rim_share=("rim", "mean"))
        .reset_index()
    )
    game.to_csv(ROOT / "results/rim_game_rates.csv", index=False)
    d[
        [
            "GAME_ID",
            "GAME_EVENT_ID",
            "PLAYER_NAME",
            "opponent",
            "Wembanyama",
            "rim",
            "made",
            "points",
            "margin",
            "PERIOD",
            "seconds",
            "prior_rim_share",
        ]
    ].to_csv(ROOT / "data/rim_model_rows.csv.gz", index=False)
    summary = {
        "games": d.GAME_ID.nunique(),
        "opponent_attempts": len(d),
        "rim_attempts": int(d.rim.sum()),
        "bootstrap_replicates": 2000,
        "comparison": "Within games with both Wembanyama-on and Wembanyama-off opponent attempts",
        "primary": estimates[1],
    }
    save_json("rim_summary.json", summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
