"""Rebuild analysis tables, SQL views, figures and articles from pinned inputs."""

import argparse
from . import data, lineups, rim_footprint, guard_groups, playoff_diet, figures, publish
from .common import ROOT


def run(fetch=False):
    for folder in ["results", "figures", "data/raw"]:
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    if fetch:
        data.fetch()
    for name, function in [
        ("Lineup audit", lineups.run),
        ("SQL", data.database),
        ("Rim footprint", rim_footprint.run),
        ("Guard groups", guard_groups.run),
        ("Playoff diet", playoff_diet.run),
        ("Figures", figures.run),
        ("Articles", publish.run),
    ]:
        function()
        print(name, "complete", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--fetch", action="store_true")
    run(p.parse_args().fetch)
