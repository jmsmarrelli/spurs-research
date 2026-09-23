import json
import numpy as np
import pandas as pd
from .common import ROOT, shots, TEAM, save_json, SEED

WEMBY = 1641705
ZONES = ["Restricted area", "Other paint", "Midrange", "Three-pointer"]


def classify(d):
    out = d.copy()
    out["zone"] = out.SHOT_ZONE_BASIC.replace(
        {
            "Restricted Area": "Restricted area",
            "In The Paint (Non-RA)": "Other paint",
            "Mid-Range": "Midrange",
            "Left Corner 3": "Corner three",
            "Right Corner 3": "Corner three",
            "Above the Break 3": "Above-break three",
            "Backcourt": "Other",
        }
    )
    mismatch = (
        out.three & ~out.zone.isin(["Corner three", "Above-break three", "Other"])
    ) | (
        ~out.three
        & out.zone.isin(["Restricted area", "Other paint", "Midrange"]).eq(False)
    )
    out.loc[mismatch, "zone"] = "Other"
    out["zone"] = out.zone.replace(
        {"Corner three": "Three-pointer", "Above-break three": "Three-pointer"}
    )
    return out


def read_playoffs():
    d = pd.read_csv(ROOT / "data/raw/shotdetail_po_2025.csv")
    assert not d.duplicated(["GAME_ID", "GAME_EVENT_ID"]).any()
    d["date"] = pd.to_datetime(d.GAME_DATE.astype(str), format="%Y%m%d")
    d["team"] = d.TEAM_ID.map(TEAM)
    d["opponent"] = np.where(d.team == d.HTM, d.VTM, d.HTM)
    d["made"] = d.SHOT_MADE_FLAG
    d["three"] = d.SHOT_TYPE.eq("3PT Field Goal")
    d["points"] = d.made * np.where(d.three, 3, 2)
    return classify(d)


def weighted_profile(d, opponent_weights):
    group = (
        d.groupby(["opponent", "zone"])
        .agg(n=("made", "size"), points=("points", "sum"))
        .reindex(
            pd.MultiIndex.from_product(
                [opponent_weights.index, ZONES], names=["opponent", "zone"]
            ),
            fill_value=0,
        )
    )
    totals = group.groupby("opponent").n.transform("sum")
    group["attempt_weight"] = (
        group.n
        / totals
        * group.index.get_level_values("opponent").map(opponent_weights)
    )
    group["point_weight"] = (
        group.points
        / totals
        * group.index.get_level_values("opponent").map(opponent_weights)
    )
    z = group.groupby("zone")[["attempt_weight", "point_weight"]].sum().reindex(ZONES)
    z["ppa"] = np.divide(
        z.point_weight,
        z.attempt_weight,
        out=np.zeros(len(z)),
        where=z.attempt_weight > 0,
    )
    assert abs(z.attempt_weight.sum() - 1) < 1e-10, "Opponent weights must sum to one"
    return z


def decomposition(a, b):
    mix = ((b.attempt_weight - a.attempt_weight) * (b.ppa + a.ppa) / 2).sum()
    conversion = ((b.ppa - a.ppa) * (b.attempt_weight + a.attempt_weight) / 2).sum()
    return np.array([mix, conversion, b.point_weight.sum() - a.point_weight.sum()])


def run():
    regular = classify(shots(2025))
    post = read_playoffs()
    r = regular[regular.PLAYER_ID.eq(WEMBY)].copy()
    p = post[post.PLAYER_ID.eq(WEMBY)].copy()
    unsupported = sorted(set(p.opponent) - set(r.opponent))
    excluded_opponent_attempts = int(p.opponent.isin(unsupported).sum())
    p = p[~p.opponent.isin(unsupported)].copy()
    excluded_zone_attempts = int((~p.zone.isin(ZONES)).sum())
    r = r[r.zone.isin(ZONES)]
    p = p[p.zone.isin(ZONES)]
    opponents = p.opponent.value_counts(normalize=True).sort_index()
    r = r[r.opponent.isin(opponents.index)]
    if not set(opponents.index) <= set(r.opponent):
        raise ValueError("Opponent has no regular-season support")
    a = weighted_profile(r, opponents)
    b = weighted_profile(p, opponents)
    profile = pd.concat(
        [a.assign(phase="Matched regular season"), b.assign(phase="Playoffs")]
    ).reset_index()
    profile.to_csv(ROOT / "results/playoff_zone_profiles.csv", index=False)
    effect = decomposition(a, b)
    rng = np.random.default_rng(SEED)
    draws = []
    # Bootstrap game sufficient statistics within opponent strata, retaining the
    # observed playoff-opponent weights rather than changing the comparison.
    cubes = []
    for frame in [r, p]:
        by_opp = {}
        for opp, g in frame.groupby("opponent"):
            z = (
                g.groupby(["GAME_ID", "zone"])
                .agg(n=("made", "size"), points=("points", "sum"))
                .unstack(fill_value=0)
            )
            counts = z["n"].reindex(columns=ZONES, fill_value=0).to_numpy()
            points = z["points"].reindex(columns=ZONES, fill_value=0).to_numpy()
            by_opp[opp] = (counts, points)
        cubes.append(by_opp)

    def sampled_profile(groups):
        weights = np.zeros(len(ZONES))
        points = np.zeros(len(ZONES))
        for opp, (n, pts) in groups.items():
            ix = rng.integers(0, len(n), len(n))
            nn = n[ix].sum(axis=0)
            pp = pts[ix].sum(axis=0)
            weights += opponents[opp] * nn / nn.sum()
            points += opponents[opp] * pp / nn.sum()
        return pd.DataFrame(
            {
                "attempt_weight": weights,
                "point_weight": points,
                "ppa": np.divide(
                    points, weights, out=np.zeros(len(weights)), where=weights > 0
                ),
            },
            index=ZONES,
        )

    for _ in range(2000):
        draws.append(
            decomposition(sampled_profile(cubes[0]), sampled_profile(cubes[1]))
        )
    interval = np.quantile(draws, [0.025, 0.975], axis=0)
    table = pd.DataFrame(
        {
            "component": [
                "Shot-location mix",
                "Within-zone conversion",
                "Total FG scoring change",
            ],
            "estimate": effect,
            "lower": interval[0],
            "upper": interval[1],
        }
    )
    table.to_csv(ROOT / "results/playoff_decomposition.csv", index=False)
    rows = []
    for opp in opponents.index:
        x = r[r.opponent.eq(opp)]
        y = p[p.opponent.eq(opp)]
        rows.append(
            {
                "opponent": opp,
                "regular_games": x.GAME_ID.nunique(),
                "regular_attempts": len(x),
                "playoff_games": y.GAME_ID.nunique(),
                "playoff_attempts": len(y),
                "weight": opponents[opp],
                "regular_ppa": x.points.mean(),
                "playoff_ppa": y.points.mean(),
            }
        )
    pd.DataFrame(rows).to_csv(ROOT / "results/playoff_opponents.csv", index=False)
    trends = []
    for season in [2023, 2024, 2025]:
        g = shots(season)
        g = g[g.PLAYER_ID.eq(WEMBY)]
        trends.append(
            {
                "season": f"{season}-{str(season+1)[2:]}",
                "attempts": len(g),
                "games": g.GAME_ID.nunique(),
                "rim_share": g.SHOT_ZONE_BASIC.eq("Restricted Area").mean(),
                "three_share": g.three.mean(),
                "ppa": g.points.mean(),
            }
        )
    pd.DataFrame(trends).to_csv(ROOT / "results/wemby_regular_trend.csv", index=False)
    coords = pd.concat(
        [r.assign(phase="Matched regular season"), p.assign(phase="Playoffs")]
    )[
        [
            "GAME_ID",
            "GAME_EVENT_ID",
            "opponent",
            "phase",
            "zone",
            "LOC_X",
            "LOC_Y",
            "three",
            "made",
            "points",
        ]
    ]
    coords.to_csv(ROOT / "data/playoff_shots.csv.gz", index=False)
    summary = {
        "unsupported_opponents_excluded": unsupported,
        "unsupported_opponent_attempts_excluded": excluded_opponent_attempts,
        "inconsistent_zone_attempts_excluded": excluded_zone_attempts,
        "regular_games": r.GAME_ID.nunique(),
        "regular_attempts": len(r),
        "playoff_games": p.GAME_ID.nunique(),
        "playoff_attempts": len(p),
        "opponents": opponents.index.tolist(),
        "playoff_last_date": str(p.date.max().date()),
        "matched_regular_ppa": a.point_weight.sum(),
        "playoff_ppa": b.point_weight.sum(),
        "raw_matched_regular_ppa": r.points.mean(),
        "components": table.to_dict("records"),
        "bootstrap": "2,000 independent game resamples within each phase and opponent; playoff-opponent weights fixed",
    }
    save_json("playoff_summary.json", summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
