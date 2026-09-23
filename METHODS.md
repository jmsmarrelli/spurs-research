# Methods and data dictionary

## Shared source contract

Archive suffixes identify the starting calendar year: `2025` means 2025–26. The three regular-season shot files contain 1,230 games each. The event reconstruction uses `nbastatsv3_2025`; the playoff comparison uses `shotdetail_po_2025`. Full source URLs and SHA-256 values are in `data/source_manifest.json`.

Shot IDs are `(GAME_ID, GAME_EVENT_ID)`. Play-by-play ordering is `(gameId, actionId)`; the shot-event join uses `actionNumber`. The two event fields are not interchangeable. Player IDs are used for membership; names resolve the incoming player in substitution descriptions. A unique season-level name mapping supplies names missing from a single game's actor rows, with game mappings taking precedence.

Regular-season shots must be unique, marked as attempts, have binary outcomes and have a team matching the home or away team. Shot value comes from `SHOT_TYPE`. Points are 2 or 3 times the make indicator. “Rim” means `Restricted Area`, not a distance threshold. No calculation here treats field goal attempts as possessions.

## Reconstruction and coverage

For each period, the first observed involvement distinguishes starters from incoming substitutes. In this feed the substitution `personId` identifies the outgoing player. Blocks and steals may appear on auxiliary actor rows with no `actionType`, so those rows still establish presence. Technical events and ejections do not establish floor presence.

A period must resolve exactly five starters, all incoming and outgoing identities, five active players throughout, every live actor and the full 720-second clock (300 seconds in overtime). State after an event applies to the elapsed time until the next event. Same-clock substitutions have zero intervening elapsed time. Source order is retained; complete periods cannot contain a clock reversal.

After matching shot and event records, the shooter, shot value and made/missed result must agree. A conflict excludes that entire game. One game fails this cross-source check and one other period fails the five-starter check. Retained coverage is 325 of 330 periods and 14,642 of 14,840 shots across Spurs games. Shot linkage is complete in retained periods. Reconstructed minutes total 3,893.

These checks establish internal consistency, not independent verification against official lineups. A feed could omit a substitution without triggering every check. Official player-minute reconciliation is a remaining validation step before operational use. `results/lineup_period_audit.csv` and `results/source_disagreements.csv` identify the exclusions.

## Rim footprint

The comparison is conditional on opponent field goal attempts in games with both Wembanyama-on and Wembanyama-off attempts. The primary rim-share sample is 63 games and 5,726 attempts. Finishing uses rim attempts and reapplies the both-states requirement within that subset; see `rim_estimates.csv` for its denominator.

A linear model estimates:

`outcome = game intercept + b * Wembanyama_on + context terms + error`

Context terms are margin clipped to ±25 and divided by 25, its square, period seconds divided by 720, indicators for periods 2–5, and the shooter's prior-season rim share. The prior is `(prior rim attempts + 100 * prior league rim share) / (prior attempts + 100)`. Players without prior shots receive the league rate. Source data in this run have no retained periods above five; additional overtimes would require extending the period indicators.

Within-game centering removes game intercepts. Least squares is solved with a pseudoinverse. This is an association model, not a calibrated probability forecast, and predicted probabilities are not used. Inference resamples whole games 2,000 times and refits the coefficient using game sufficient statistics. The 2.5th and 97.5th percentiles form the reported intervals. The seed is 20260908. Sensitivity samples use 1,000 resamples. The intervals are marginal and are not adjusted for multiple comparisons.

The model does not observe opponent lineups, coverages, primary defender, fouls or possessions without an attempt. A causal rim-deterrence or points-saved interpretation is not identified. Results tables report fractions; articles multiply by 100 for percentage points or FG points per 100 attempts.

## Guard combinations and forecast validation

The three membership flags define eight mutually exclusive groups. Other players can change within each group. Minutes sum elapsed event time; shot rates use San Antonio attempts only. Group minutes cover all retained events, including those without an attempt. Group game counts in `guard_groups.csv` count games with an offensive attempt in that group.

Raw rim share and FG points per attempt receive game-cluster bootstrap intervals using 2,000 draws per group. The descriptive smoothed rim estimate adds a 100-attempt prior centered on the pre-January team rim rate. Exported `rim_low90` and `rim_high90` are conditional Beta posterior quantiles; they assume independent Bernoulli attempts and hold the prior fixed. These differ from the 95% game-bootstrap intervals used on the charts and are not a substitute for them. The full-season posterior is descriptive and is not used in the held-out evaluation.

For chronological validation, fit group rates using dates strictly before 2026-01-01 and evaluate later attempts. Both the group forecasts and the simple team baseline use only early data. The 100-attempt prior strength is prespecified, not tuned. Unseen groups receive the early team rate. The response is whether the attempt is at the rim, regardless of whether it is made. Binary log loss evaluates predictions; the paired difference is averaged and bootstrapped by later game. No group-specific predictive advantage is established by this split.

`guard_assist_connections.csv` counts credited assisted makes parsed from descriptions. It does not measure passes, potential assists or opportunity-adjusted creation. `guard_review_queue.csv` selects the first three chronological attempts in each group. It is a location aid, not a random or representative sample and not completed video coding. Game pages may not provide playable video for every event.

## Playoff comparison and decomposition

Only opponents with Wembanyama attempts in both the regular season and playoffs enter the matched comparison. Portland has no regular-season support and its 48 playoff attempts are excluded. One playoff attempt has a zone/value disagreement. Four zones remain: restricted area, other paint, midrange and all three-pointers. Unclassified and backcourt attempts are excluded from this comparison.

Opponent weights equal each opponent's share of retained playoff attempts. Both phases use these same weights. Within each opponent, attempts and points are divided by that opponent's attempts; the results are then summed using opponent weights. The resulting zone attempt weights sum to one. Points per attempt within a zone are weighted zone points divided by weighted zone attempts.

For phase R (regular) and P (playoff), zone share w and within-zone scoring p:

`mix = sum((wP - wR) * (pP + pR) / 2)`

`conversion = sum((pP - pR) * (wP + wR) / 2)`

`mix + conversion = sum(wP * pP) - sum(wR * pR)`

This is a symmetric arithmetic decomposition, not an estimate of a coaching intervention. All observed aggregate zones have support in both phases. A bootstrap draw with no observations in a zone assigns zero within-zone scoring to that empty zone; the product stays zero and the identity still holds, but component allocation in such draws is convention-dependent. Sparse support is another reason to avoid strong conclusions from component intervals.

The bootstrap independently resamples games within each phase/opponent stratum 2,000 times, holding the observed opponent weights fixed. The regular-season strata contain only 2, 2 and 5 games. Intervals condition on this narrow historical schedule and cannot capture unobserved matchup variation. The total-change interval crosses zero.

Coordinates are divided by ten to plot feet on a reference court. Every dot is an attempt; the map is unweighted and does not normalize visual density across unequal samples. Weighted rates are in the separate profile chart. No defender distance, shot-quality estimate, free throws or possession denominator is available.

## Derived files

| File | Unit | Key fields |
| --- | --- | --- |
| `data/spurs_shots.csv.gz` | Matched shot in a retained period | Source shot fields, lineup IDs, target flags, pre-event margin |
| `data/spurs_events.csv.gz` | Retained event | Game/order IDs, period, clock, elapsed seconds, lineup and flags |
| `data/rim_model_rows.csv.gz` | Opponent attempt in the primary comparison | On/off flag, rim/make indicators, context and prior |
| `data/playoff_shots.csv.gz` | Wembanyama attempt in matched phases | Opponent, phase, zone, coordinates, outcome |
| `results/sql_guard_stints.csv` | Full-five stint within a period | Ordered boundary IDs and duration |

SQL has unique indexes on shot and ordered event keys. Window functions find changes in the full five and cumulative stint numbers. Tests reconcile SQL attempts and duration with the Python-derived records.
