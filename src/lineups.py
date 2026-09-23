"""Reconstruct San Antonio's five players from period appearances and substitutions.

A period is retained only when its starting five and every substitution resolve
without contradiction. The reconstruction is deliberately fail-closed.
"""

import re, json
import numpy as np
import pandas as pd
from .common import ROOT, shots, save_json

SPURS = 1610612759
TARGETS = {"Wembanyama": 1641705, "Fox": 1628368, "Castle": 1642264, "Harper": 1642844}


def seconds(clock):
    match = re.fullmatch(r"PT(\d+)M([\d.]+)S", clock)
    if not match:
        raise ValueError(f"Invalid clock: {clock}")
    return int(match[1]) * 60 + float(match[2])


def substitutions(frame):
    mapping = {}
    for name, g in frame[frame.teamId.eq(SPURS) & frame.personId.gt(0)].groupby(
        "playerName"
    ):
        ids = g.personId.unique()
        if len(ids) == 1:
            mapping[name] = int(ids[0])
    return mapping


def reconstruct_period(period, mapping):
    p = period.sort_values("actionId").copy()
    if p.actionId.duplicated().any():
        return None, "duplicate order"
    team = p[p.teamId.eq(SPURS) & p.personId.gt(0)]
    first = {}
    swaps = {}
    for i, row in team.iterrows():
        if row.actionType == "Substitution":
            m = re.fullmatch(r"SUB: (.+) FOR (.+)", str(row.description))
            if not m or m[1] not in mapping or m[2] not in mapping:
                return None, "unresolved substitution"
            incoming, outgoing = mapping[m[1]], mapping[m[2]]
            if outgoing != int(row.personId):
                return None, "outgoing ID mismatch"
            first.setdefault(incoming, False)
            first.setdefault(outgoing, True)
            swaps[i] = (incoming, outgoing)
        elif ("Technical" not in str(row.subType)) and row.actionType not in [
            "Ejection"
        ]:
            # Actor rows for blocks and steals have a missing actionType in this feed.
            first.setdefault(int(row.personId), True)
    on = {player for player, active in first.items() if active}
    if len(on) != 5:
        return None, f"{len(on)} inferred starters"
    flags = []
    lineups = []
    for i, row in p.iterrows():
        if i in swaps:
            incoming, outgoing = swaps[i]
            if outgoing not in on or incoming in on:
                return None, "substitution contradiction"
            on.remove(outgoing)
            on.add(incoming)
        elif (
            row.teamId == SPURS
            and row.personId > 0
            and row.actionType not in ["Ejection"]
            and "Technical" not in str(row.subType)
        ):
            if int(row.personId) not in on:
                return None, "inactive actor"
        flags.append({name: int(pid in on) for name, pid in TARGETS.items()})
        lineups.append("|".join(map(str, sorted(on))))
    for name in TARGETS:
        p[name] = [f[name] for f in flags]
    p["lineup"] = lineups
    return p, "valid"


def run():
    raw = pd.read_csv(ROOT / "data/raw/nbastatsv3_2025.csv", low_memory=False)
    ids = raw.loc[raw.teamId.eq(SPURS), "gameId"].unique()
    raw = raw[raw.gameId.isin(ids)].copy()
    valid = []
    checks = []
    season_mapping = substitutions(raw)
    for game, g in raw.groupby("gameId"):
        mapping = {**season_mapping, **substitutions(g)}
        for number, period in g.groupby("period"):
            p, status = reconstruct_period(period, mapping)
            checks.append(
                {
                    "game_id": game,
                    "period": number,
                    "status": status,
                    "events": len(period),
                    "fga": int(period.isFieldGoal.sum()),
                }
            )
            if p is None:
                continue
            p["seconds"] = p.clock.map(seconds)
            # State is after each event; it applies to elapsed time until the next event.
            next_clock = p.seconds.shift(-1).fillna(0)
            elapsed = p.seconds - next_clock
            if (elapsed < -0.01).any():
                checks[-1]["status"] = "nonmonotonic clock"
                continue
            p["elapsed"] = elapsed.clip(lower=0)
            if abs(p.elapsed.sum() - (720 if number <= 4 else 300)) > 0.1:
                checks[-1]["status"] = "incomplete period time"
                continue
            p["scoreHome_before"] = p.scoreHome.ffill().shift(1).fillna(0)
            p["scoreAway_before"] = p.scoreAway.ffill().shift(1).fillna(0)
            # Score starts for later periods come from game-level forward fill below.
            valid.append(p)
    events = pd.concat(valid).sort_values(["gameId", "actionId"])
    scores = raw.sort_values(["gameId", "actionId"]).copy()
    for column in ["scoreHome", "scoreAway"]:
        scores[column + "_before"] = scores.groupby("gameId")[column].transform(
            lambda s: s.ffill().shift(1).fillna(0)
        )
    events = events.drop(columns=["scoreHome_before", "scoreAway_before"]).merge(
        scores[["gameId", "actionId", "scoreHome_before", "scoreAway_before"]],
        on=["gameId", "actionId"],
        validate="one_to_one",
    )
    s = shots(2025)
    s = s[s.GAME_ID.isin(ids)]
    home = s.groupby("GAME_ID").HTM.first().eq("SAS")
    events["margin"] = np.where(
        events.gameId.map(home),
        events.scoreHome_before - events.scoreAway_before,
        events.scoreAway_before - events.scoreHome_before,
    )
    fg = events[events.isFieldGoal.eq(1)].copy()
    assert not fg.duplicated(["gameId", "actionNumber"]).any()
    keep = [
        "gameId",
        "actionNumber",
        "period",
        "clock",
        "seconds",
        "margin",
        "lineup",
    ] + list(TARGETS)
    matched = s.merge(
        fg[keep],
        left_on=["GAME_ID", "GAME_EVENT_ID"],
        right_on=["gameId", "actionNumber"],
        how="inner",
        validate="one_to_one",
    )
    # A shot in a period is only included if it reconciles with the play-by-play actor/value.
    audit = fg.merge(
        s[["GAME_ID", "GAME_EVENT_ID", "PLAYER_ID", "made", "three"]],
        left_on=["gameId", "actionNumber"],
        right_on=["GAME_ID", "GAME_EVENT_ID"],
        how="inner",
        validate="one_to_one",
    )
    agrees = (
        audit.personId.eq(audit.PLAYER_ID)
        & audit.shotValue.eq(np.where(audit.three, 3, 2))
        & audit.shotResult.eq(np.where(audit.made, "Made", "Missed"))
    )
    bad_games = set(audit.loc[~agrees, "gameId"])
    audit.loc[
        ~agrees,
        [
            "gameId",
            "actionNumber",
            "personId",
            "PLAYER_ID",
            "description",
            "shotValue",
            "shotResult",
            "made",
        ],
    ].to_csv(ROOT / "results/source_disagreements.csv", index=False)
    # Exclude the whole game if either feed identifies a different shot at an event ID.
    events = events[~events.gameId.isin(bad_games)]
    matched = matched[~matched.GAME_ID.isin(bad_games)]
    for c in checks:
        if c["game_id"] in bad_games:
            c["status"] = "cross-source game disagreement"
    pd.DataFrame(checks).to_csv(ROOT / "results/lineup_period_audit.csv", index=False)
    matched.to_csv(ROOT / "data/spurs_shots.csv.gz", index=False)
    events[
        [
            "gameId",
            "actionNumber",
            "actionId",
            "period",
            "clock",
            "seconds",
            "elapsed",
            "margin",
            "teamId",
            "personId",
            "actionType",
            "description",
            "lineup",
        ]
        + list(TARGETS)
    ].to_csv(ROOT / "data/spurs_events.csv.gz", index=False)
    minutes = []
    for name in TARGETS:
        minutes.append(
            {
                "player": name,
                "minutes": float((events.elapsed * events[name]).sum() / 60),
            }
        )
    pd.DataFrame(minutes).to_csv(
        ROOT / "results/reconstructed_minutes.csv", index=False
    )
    summary = {
        "spurs_games": len(ids),
        "cross_source_games_excluded": len(bad_games),
        "retained_games": matched.GAME_ID.nunique(),
        "periods_total": len(checks),
        "periods_retained": sum(c["status"] == "valid" for c in checks),
        "eligible_fga": len(matched),
        "all_spurs_game_fga": len(s),
        "shot_coverage": len(matched) / len(s),
        "fg_linkage_in_valid_periods": len(matched)
        / len(fg[~fg.gameId.isin(bad_games)]),
        "status_counts": pd.Series([c["status"] for c in checks])
        .value_counts()
        .to_dict(),
        "substitution_checks": "Five starters, outgoing identity, active actors, and complete period clock required",
    }
    save_json("lineup_summary.json", summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
