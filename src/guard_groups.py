import json
import numpy as np
import pandas as pd
from scipy.stats import beta
from .common import ROOT, save_json, SEED, logloss, paired_loss_ci

NAMES = ["Fox", "Castle", "Harper"]


def group_label(row):
    names = [name for name in NAMES if row[name] == 1]
    return " + ".join(names) if names else "None of the three"


def run():
    events = pd.read_csv(ROOT / "data/spurs_events.csv.gz")
    d = pd.read_csv(ROOT / "data/spurs_shots.csv.gz", parse_dates=["date"])
    events["group"] = events.apply(group_label, axis=1)
    d["group"] = d.apply(group_label, axis=1)
    offense = d[d.team.eq("SAS")].copy()
    offense["rim"] = offense.SHOT_ZONE_BASIC.eq("Restricted Area").astype(int)
    league_prior = offense[offense.date < "2026-01-01"].rim.mean()
    early = offense[offense.date < "2026-01-01"]
    later = offense[offense.date >= "2026-01-01"]
    counts = early.groupby("group").rim.agg(["sum", "count"])
    forecasts = (counts["sum"] + 100 * league_prior) / (counts["count"] + 100)
    # A prespecified 100-attempt prior tempers tiny groups; it is not tuned on later results.
    rows = []
    for label, g in offense.groupby("group"):
        ev = events[events.group == label]
        a = early[early.group == label]
        b = later[later.group == label]
        alpha = g.rim.sum() + 100 * league_prior
        beta_ = len(g) - g.rim.sum() + 100 * (1 - league_prior)
        game = (
            g.groupby("GAME_ID")
            .agg(points=("points", "sum"), n=("made", "size"), rim=("rim", "sum"))
            .to_numpy()
        )
        rng = np.random.default_rng(SEED)
        sim = []
        rim_sim = []
        for _ in range(2000):
            t = game[rng.integers(0, len(game), len(game))].sum(axis=0)
            sim.append(t[0] / t[1])
            rim_sim.append(t[2] / t[1])
        lo, hi = np.quantile(sim, [0.025, 0.975])
        rows.append(
            {
                "group": label,
                "minutes": ev.elapsed.sum() / 60,
                "games": g.GAME_ID.nunique(),
                "attempts": len(g),
                "rim_share": g.rim.mean(),
                "rim_boot_low": np.quantile(rim_sim, 0.025),
                "rim_boot_high": np.quantile(rim_sim, 0.975),
                "three_share": g.three.mean(),
                "ppa": g.points.mean(),
                "ppa_low": lo,
                "ppa_high": hi,
                "wemby_shot_share": g.Wembanyama.mean(),
                "rim_posterior": alpha / (alpha + beta_),
                "rim_low90": beta.ppf(0.05, alpha, beta_),
                "rim_high90": beta.ppf(0.95, alpha, beta_),
                "early_attempts": len(a),
                "late_attempts": len(b),
                "early_rim_forecast": forecasts.get(label, league_prior),
                "late_rim_share": b.rim.mean(),
            }
        )
    table = pd.DataFrame(rows).sort_values("minutes", ascending=False)
    table.to_csv(ROOT / "results/guard_groups.csv", index=False)
    parts = (
        offense.groupby(["group", "Wembanyama"])
        .agg(
            attempts=("made", "size"), rim_share=("rim", "mean"), ppa=("points", "mean")
        )
        .reset_index()
    )
    parts.to_csv(ROOT / "results/guard_wemby_splits.csv", index=False)
    owners = (
        offense[
            offense.PLAYER_NAME.isin(["De'Aaron Fox", "Stephon Castle", "Dylan Harper"])
        ]
        .groupby(["group", "PLAYER_NAME"])
        .agg(
            attempts=("made", "size"),
            rim_share=("rim", "mean"),
            three_share=("three", "mean"),
        )
        .reset_index()
    )
    owners.to_csv(ROOT / "results/guard_shot_ownership.csv", index=False)
    # Resolve assisted makes only; assists are not a count of passes or creation opportunities.
    makes = events[
        events.teamId.eq(1610612759) & events.actionType.eq("Made Shot")
    ].copy()
    makes["assist_name"] = makes.description.str.extract(
        r"\(([^()]+?) \d+ AST\)", expand=False
    )
    passing = makes[makes.assist_name.isin(NAMES)].copy()
    passing["receiver"] = passing.personId.map(
        offense.drop_duplicates("PLAYER_ID").set_index("PLAYER_ID").PLAYER_NAME
    )
    edges = (
        passing.groupby(["assist_name", "receiver"])
        .size()
        .rename("assisted_makes")
        .reset_index()
    )
    edges.to_csv(ROOT / "results/guard_assist_connections.csv", index=False)
    candidates = []
    for label, g in offense.groupby("group"):
        for _, r in g.head(3).iterrows():
            candidates.append(
                {
                    "group": label,
                    "game_id": r.GAME_ID,
                    "event_id": r.GAME_EVENT_ID,
                    "period": r.PERIOD,
                    "clock": r.clock,
                    "shooter": r.PLAYER_NAME,
                    "lineup_ids": r.lineup,
                    "url": f"https://www.nba.com/game/{r.GAME_ID:010d}/play-by-play",
                }
            )
    pd.DataFrame(candidates).to_csv(
        ROOT / "results/guard_review_queue.csv", index=False
    )
    later = later.copy()
    later["forecast"] = later["group"].map(forecasts).fillna(league_prior)
    prior_pred = np.repeat(league_prior, len(later))
    comparison = later.drop(columns="made").rename(columns={"rim": "made"})
    validation = {
        "later_attempts": len(later),
        "pooled_group_logloss": logloss(later.rim, later.forecast),
        "early_team_logloss": logloss(later.rim, prior_pred),
        "loss_difference": paired_loss_ci(comparison, later.forecast, prior_pred),
    }
    save_json("guard_validation.json", validation)
    triple = table[table.group.eq("Fox + Castle + Harper")].iloc[0].to_dict()
    summary = {
        "guard_combinations": len(table),
        "team_attempts": len(offense),
        "reconstructed_minutes": events.elapsed.sum() / 60,
        "three_guard_group": triple,
        "early_rim_prior": league_prior,
        "prior_strength": 100,
        "assisted_makes_by_guards": len(passing),
    }
    save_json("guards_summary.json", summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
