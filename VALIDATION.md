# Delivered run

The full analysis pipeline completed from five checksum-verified source archives. All three notebooks executed successfully, with four populated code cells each and no error outputs. Fifteen automated tests passed locally.

Checks cover substitution direction and active players, complete period clocks, unique event IDs, cross-feed shot clocks, five-player membership flags, guard-group totals, chronological forecast inputs, opponent support, the decomposition identity and SQL reconciliation of attempts and minutes.

Nine figures were inspected visually. Articles contain their three figures as embedded images, with no external image requirement.

The main data limitation is that internally consistent reconstructed lineups have not been independently reconciled against official box-score minutes. The three-guard sample contains only 46 attempts. The matched playoff baseline contains only nine regular-season games. These limitations are included in the articles and methods.

See `data/source_manifest.json` for exact inputs, `results/lineup_period_audit.csv` for exclusions and `METHODS.md` for denominators and inference assumptions.
