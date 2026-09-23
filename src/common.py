from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260908
TEAM = {
    1610612737: "ATL",
    1610612738: "BOS",
    1610612739: "CLE",
    1610612740: "NOP",
    1610612741: "CHI",
    1610612742: "DAL",
    1610612743: "DEN",
    1610612744: "GSW",
    1610612745: "HOU",
    1610612746: "LAC",
    1610612747: "LAL",
    1610612748: "MIA",
    1610612749: "MIL",
    1610612750: "MIN",
    1610612751: "BKN",
    1610612752: "NYK",
    1610612753: "ORL",
    1610612754: "IND",
    1610612755: "PHI",
    1610612756: "PHX",
    1610612757: "POR",
    1610612758: "SAC",
    1610612759: "SAS",
    1610612760: "OKC",
    1610612761: "TOR",
    1610612762: "UTA",
    1610612763: "MEM",
    1610612764: "WAS",
    1610612765: "DET",
    1610612766: "CHA",
}


def shots(season):
    d = pd.read_csv(ROOT / f"data/raw/shotdetail_{season}.csv")
    if d.duplicated(["GAME_ID", "GAME_EVENT_ID"]).any():
        raise ValueError("Duplicate shot event")
    if not d.SHOT_MADE_FLAG.isin([0, 1]).all():
        raise ValueError("Invalid outcome")
    if not d.SHOT_ATTEMPTED_FLAG.eq(1).all():
        raise ValueError("Non-attempt row")
    d["date"] = pd.to_datetime(d.GAME_DATE.astype(str), format="%Y%m%d")
    d["team"] = d.TEAM_ID.map(TEAM)
    if d.team.isna().any():
        raise ValueError("Unknown team ID")
    d["opponent"] = np.where(d.team == d.HTM, d.VTM, d.HTM)
    if not (d.team.eq(d.HTM) | d.team.eq(d.VTM)).all():
        raise ValueError("Home/away mismatch")
    d["three"] = d.SHOT_TYPE.eq("3PT Field Goal")
    d["corner"] = d.SHOT_ZONE_BASIC.isin(["Left Corner 3", "Right Corner 3"]).astype(
        int
    )
    d["heave"] = d.SHOT_DISTANCE.ge(40)
    d["made"] = d.SHOT_MADE_FLAG
    d["points"] = d.made * np.where(d.three, 3, 2)
    return d.sort_values(["date", "GAME_ID", "GAME_EVENT_ID"]).reset_index(drop=True)


def save_json(name, obj):
    (ROOT / "results" / name).write_text(
        json.dumps(obj, indent=2, default=lambda x: float(x))
    )


def cluster_mean_ci(frame, value, cluster="GAME_ID", reps=2000):
    g = frame.groupby(cluster)[value].agg(["sum", "count"]).to_numpy()
    rng = np.random.default_rng(SEED)
    estimates = []
    for _ in range(reps):
        a = g[rng.integers(0, len(g), len(g))]
        estimates.append(a[:, 0].sum() / a[:, 1].sum())
    return np.quantile(estimates, [0.025, 0.975])


def logloss(y, p):
    p = np.clip(np.asarray(p), 1e-6, 1 - 1e-6)
    y = np.asarray(y)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log1p(-p)))


def paired_loss_ci(frame, a, b):
    y = frame.made.to_numpy()

    def loss(p):
        p = np.clip(np.asarray(p), 1e-6, 1 - 1e-6)
        return -(y * np.log(p) + (1 - y) * np.log1p(-p))

    f = frame[["GAME_ID"]].copy()
    f["difference"] = loss(a) - loss(b)
    lo, hi = cluster_mean_ci(f, "difference")
    return {
        "difference": float(f.difference.mean()),
        "lower": float(lo),
        "upper": float(hi),
    }
