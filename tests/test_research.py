import json
import sqlite3
import unittest

import numpy as np
import pandas as pd

from src.common import ROOT
from src.data import database
from src.guard_groups import group_label
from src.lineups import SPURS, TARGETS, reconstruct_period, seconds
from src.playoff_diet import ZONES, decomposition, weighted_profile
from src.rim_footprint import within_game


class ReconstructionTests(unittest.TestCase):
    def fixture(self):
        rows = []
        for player in range(1, 6):
            rows.append(
                dict(
                    actionId=len(rows),
                    teamId=SPURS,
                    personId=player,
                    actionType="Made Shot",
                    subType="",
                    description="Shot",
                )
            )
        rows.append(
            dict(
                actionId=5,
                teamId=SPURS,
                personId=1,
                actionType="Substitution",
                subType="",
                description="SUB: Six FOR One",
            )
        )
        rows.append(
            dict(
                actionId=6,
                teamId=SPURS,
                personId=6,
                actionType="Missed Shot",
                subType="",
                description="Missed shot",
            )
        )
        return pd.DataFrame(rows), {"One": 1, "Six": 6}

    def test_substitution_changes_exactly_one_player(self):
        rows, mapping = self.fixture()
        result, status = reconstruct_period(rows, mapping)
        self.assertEqual(status, "valid")
        self.assertEqual(result.iloc[0].lineup, "1|2|3|4|5")
        self.assertEqual(result.iloc[-1].lineup, "2|3|4|5|6")

    def test_unresolved_incoming_name_rejects_period(self):
        rows, mapping = self.fixture()
        result, status = reconstruct_period(rows, {"One": 1})
        self.assertIsNone(result)
        self.assertEqual(status, "unresolved substitution")

    def test_wrong_outgoing_id_rejects_period(self):
        rows, mapping = self.fixture()
        rows.loc[5, "personId"] = 2
        result, status = reconstruct_period(rows, mapping)
        self.assertIsNone(result)
        self.assertEqual(status, "outgoing ID mismatch")

    def test_actor_after_substitution_is_rejected(self):
        rows, mapping = self.fixture()
        rows.loc[6, "personId"] = 1
        result, status = reconstruct_period(rows, mapping)
        self.assertIsNone(result)
        self.assertEqual(status, "inactive actor")

    def test_clock_format(self):
        self.assertAlmostEqual(seconds("PT01M23.50S"), 83.5)
        with self.assertRaises(ValueError):
            seconds("01:23")


class MathematicalTests(unittest.TestCase):
    def test_game_effects_remove_between_game_confounding(self):
        # Game-specific baselines correlate with on-court exposure; true within-game b is 2.
        rows = []
        for game in range(1, 9):
            for flag in [0] * game + [1] * (10 - game):
                rows.append(
                    {"GAME_ID": game, "Wembanyama": flag, "y": game * 10 + 2 * flag}
                )
        fit = within_game(pd.DataFrame(rows), "y", controls=False, reps=100)
        self.assertAlmostEqual(fit["estimate"], 2)
        self.assertAlmostEqual(fit["lower"], 2)
        self.assertAlmostEqual(fit["upper"], 2)

    def test_decomposition_identity_with_changed_shares_and_accuracy(self):
        a = pd.DataFrame(
            {"attempt_weight": [0.4, 0.1, 0.2, 0.3], "ppa": [1.4, 0.8, 0.9, 1.1]}
        )
        b = pd.DataFrame(
            {"attempt_weight": [0.3, 0.2, 0.1, 0.4], "ppa": [1.3, 0.9, 0.7, 1.0]}
        )
        for d in [a, b]:
            d["point_weight"] = d.attempt_weight * d.ppa
        parts = decomposition(a, b)
        self.assertAlmostEqual(parts[0] + parts[1], parts[2])
        np.testing.assert_allclose(decomposition(b, a), -parts, atol=1e-12)

    def test_opponent_weighting_does_not_use_unweighted_attempt_mix(self):
        d = pd.DataFrame(
            {
                "opponent": ["A", "A", "B"],
                "zone": [ZONES[0]] * 3,
                "made": [1, 1, 0],
                "points": [2, 2, 0],
            }
        )
        z = weighted_profile(d, pd.Series({"A": 0.25, "B": 0.75}))
        self.assertAlmostEqual(z.attempt_weight.sum(), 1)
        self.assertAlmostEqual(z.point_weight.sum(), 0.5)
        with self.assertRaises((AssertionError, ValueError)):
            weighted_profile(d, pd.Series({"A": 0.25, "C": 0.75}))


class DeliveredDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shots = pd.read_csv(ROOT / "data/spurs_shots.csv.gz")
        cls.events = pd.read_csv(ROOT / "data/spurs_events.csv.gz")
        cls.groups = pd.read_csv(ROOT / "results/guard_groups.csv")

    def test_event_uniqueness_and_shot_period_clock_agreement(self):
        self.assertFalse(self.shots.duplicated(["GAME_ID", "GAME_EVENT_ID"]).any())
        self.assertFalse(self.events.duplicated(["gameId", "actionId"]).any())
        self.assertTrue(self.shots.PERIOD.eq(self.shots.period).all())
        # Shot-detail uses whole seconds; the event clock can retain hundredths.
        delta = (
            self.shots.MINUTES_REMAINING * 60
            + self.shots.SECONDS_REMAINING
            - self.shots.seconds
        )
        self.assertTrue(delta.abs().lt(1).all())

    def test_every_lineup_has_five_and_flags_match_ids(self):
        for lineup in self.events.lineup.unique():
            self.assertEqual(len(set(lineup.split("|"))), 5)
        for name, player in TARGETS.items():
            expected = self.events.lineup.str.split("|").map(
                lambda ids: int(str(player) in ids)
            )
            np.testing.assert_array_equal(expected, self.events[name])

    def test_complete_period_time_and_audit_exclusions(self):
        times = self.events.groupby(["gameId", "period"]).elapsed.sum()
        for (_, period), duration in times.items():
            self.assertAlmostEqual(duration, 720 if period <= 4 else 300)
        self.assertTrue(self.events.elapsed.ge(0).all())
        audit = pd.read_csv(ROOT / "results/lineup_period_audit.csv")
        bad = audit[audit.status.ne("valid")]
        retained = set(zip(self.events.gameId, self.events.period))
        self.assertFalse(retained & set(zip(bad.game_id, bad.period)))

    def test_guard_partition_and_time_totals(self):
        self.assertEqual(len(self.groups), 8)
        offense = self.shots[self.shots.team.eq("SAS")]
        labels = offense.apply(group_label, axis=1).value_counts().sort_index()
        actual = self.groups.set_index("group").attempts.sort_index()
        np.testing.assert_array_equal(labels, actual)
        self.assertEqual(int(actual.sum()), len(offense))
        self.assertAlmostEqual(
            self.groups.minutes.sum(), self.events.elapsed.sum() / 60
        )

    def test_chronological_forecasts_recompute_from_early_shots(self):
        offense = self.shots[self.shots.team.eq("SAS")].copy()
        offense["group"] = offense.apply(group_label, axis=1)
        early = offense[offense.date.lt("2026-01-01")].copy()
        early["rim"] = early.SHOT_ZONE_BASIC.eq("Restricted Area")
        prior = early.rim.mean()
        for _, row in self.groups.iterrows():
            sample = early[early.group.eq(row["group"])]
            expected = (sample.rim.sum() + 100 * prior) / (len(sample) + 100)
            self.assertAlmostEqual(row.early_rim_forecast, expected)
        triple = self.groups[self.groups.group.eq("Fox + Castle + Harper")].iloc[0]
        self.assertEqual(triple.early_attempts, 0)
        self.assertAlmostEqual(triple.early_rim_forecast, prior)

    def test_playoff_support_and_reported_decomposition(self):
        d = pd.read_csv(ROOT / "data/playoff_shots.csv.gz")
        summary = json.loads((ROOT / "results/playoff_summary.json").read_text())
        r = d[d.phase.eq("Matched regular season")]
        p = d[d.phase.eq("Playoffs")]
        self.assertEqual(set(r.opponent), set(p.opponent))
        self.assertNotIn("POR", set(p.opponent))
        self.assertEqual(len(r), summary["regular_attempts"])
        self.assertEqual(len(p), summary["playoff_attempts"])
        weights = p.opponent.value_counts(normalize=True).sort_index()
        values = decomposition(
            weighted_profile(r, weights), weighted_profile(p, weights)
        )
        reported = pd.read_csv(ROOT / "results/playoff_decomposition.csv")
        np.testing.assert_allclose(values, reported.estimate, atol=1e-12)
        self.assertAlmostEqual(values[0] + values[1], values[2])

    def test_sql_reconciles_shots_and_stint_minutes(self):
        database()
        with sqlite3.connect(ROOT / "data/research.sqlite") as con:
            n = con.execute("SELECT SUM(attempts) FROM guard_shot_summary").fetchone()[
                0
            ]
            minutes = con.execute("SELECT SUM(minutes) FROM guard_stints").fetchone()[0]
            opponent = con.execute(
                "SELECT SUM(attempts) FROM rim_quarter_summary"
            ).fetchone()[0]
        self.assertEqual(n, int(self.shots.team.eq("SAS").sum()))
        self.assertEqual(opponent, int(self.shots.opponent.eq("SAS").sum()))
        self.assertAlmostEqual(minutes, self.events.elapsed.sum() / 60)


if __name__ == "__main__":
    unittest.main()
