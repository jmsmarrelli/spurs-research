# Decision brief: separate rim access from rim finishing

AI-assisted synthesis of the existing study, October 22, 2026. The review protocol below is proposed; no film review or team deployment is claimed.

**Decision:** organize the Wembanyama review around how opponents reach the rim, then examine finishing conditional on getting there. Combining those questions into one field-goal percentage conceals the more precise finding.

![Adjusted rim-access and finishing comparisons with game-bootstrap intervals](../figures/rim_adjusted.png)

**Evidence:** across 63 games with observations in both on/off states, adjusted rim-attempt share is 4.6 percentage points lower during his minutes; the 95% interval is −7.0 to −2.3. The corresponding finishing estimate is −0.7 points with an interval from −5.7 to +4.2. The finishing interval is compatible with several meaningful effects; it does not prove there is no finishing effect. The denominators differ: 5,726 total opponent attempts versus 1,436 rim attempts.

**Proposed next step:** sample both successful rim entries and possessions ending elsewhere, stratified by his on/off state and game. A rim-attempt-only queue cannot show successful deterrence. Have reviewers record the initial action, help location, screening involvement, entry route and whether the possession was transition or settled offense. Include an explicit unobservable category rather than inferring a responsibility from the result.

**What would change the recommendation:** failure of the lineup audit, sensitivity to a few games, or substantial changes after accounting for role and teammate/opponent combinations. Conditioning on attempted shots can hide changes in turnovers, fouls and possessions without a field-goal attempt. The existing study cannot account for those channels as a complete defensive value model.

**Interview defense:** game fixed effects remove shared game-level differences, not lineup selection within a game. The bootstrap resamples games because attempts from the same game are dependent. A full raw-source rebuild remains blocked by omitted source files; the estimates were verified from committed model rows.

Sources: [full study](01_wembanyama_rim_footprint.md), [estimates](../results/rim_estimates.csv), [sensitivity results](../results/rim_sensitivity.csv), and [execution limits](../VALIDATION_CURRENT.md).
