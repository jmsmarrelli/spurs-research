"""Fetch pinned public inputs and build the indexed shot table used by SQL checks."""

from pathlib import Path
import argparse, hashlib, json, sqlite3, tarfile, urllib.request
import pandas as pd
from .common import ROOT, shots


def fetch():
    manifest = json.loads((ROOT / "data/source_manifest.json").read_text())
    raw = ROOT / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    for item in manifest["files"]:
        archive = raw / (item["name"] + ".tar.xz")
        if not archive.exists():
            with urllib.request.urlopen(item["url"], timeout=180) as r:
                archive.write_bytes(r.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Checksum mismatch: {archive.name}")
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                if member.isfile() and member.name.endswith(".csv"):
                    # Deliberately do not use extractall on a downloaded archive.
                    with tar.extractfile(member) as f:
                        (raw / Path(member.name).name).write_bytes(f.read())
        print(item["name"], "verified")


def database():
    d = pd.read_csv(ROOT / "data/spurs_shots.csv.gz")
    e = pd.read_csv(ROOT / "data/spurs_events.csv.gz")
    d["rim"] = d.SHOT_ZONE_BASIC.eq("Restricted Area").astype(int)
    with sqlite3.connect(ROOT / "data/research.sqlite") as con:
        d.drop(columns=["period"]).rename(columns=str.lower).to_sql(
            "shots", con, if_exists="replace", index=False
        )
        e.rename(columns=str.lower).to_sql(
            "events", con, if_exists="replace", index=False
        )
        con.execute("CREATE UNIQUE INDEX shot_event ON shots(game_id, game_event_id)")
        con.execute("CREATE UNIQUE INDEX event_order ON events(gameid, actionid)")
        con.execute("CREATE INDEX shot_team_game ON shots(team, game_id, wembanyama)")
        con.executescript((ROOT / "sql/scouting_queries.sql").read_text())
        for view in ["guard_shot_summary", "rim_quarter_summary", "guard_stints"]:
            pd.read_sql_query(f"SELECT * FROM {view}", con).to_csv(
                ROOT / f"results/sql_{view}.csv", index=False
            )
        count = con.execute("SELECT SUM(attempts) FROM guard_shot_summary").fetchone()[
            0
        ]
        assert count == int(d.team.eq("SAS").sum())
    return len(d)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["fetch", "sql"])
    args = parser.parse_args()
    if args.action == "fetch":
        fetch()
    else:
        print(database(), "shots indexed; SQL totals reconciled")
