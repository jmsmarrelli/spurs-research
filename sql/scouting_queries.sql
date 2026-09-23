-- Group membership describes the three named guards; other players can change.
DROP VIEW IF EXISTS guard_shot_summary;
CREATE VIEW guard_shot_summary AS
SELECT fox, castle, harper, COUNT(*) AS attempts,
       COUNT(DISTINCT game_id) AS games, AVG(rim) AS rim_share,
       AVG(points) AS fg_points_per_attempt
FROM shots WHERE team = 'SAS'
GROUP BY fox, castle, harper;

DROP VIEW IF EXISTS rim_quarter_summary;
CREATE VIEW rim_quarter_summary AS
SELECT game_id, period, wembanyama, COUNT(*) AS attempts,
       SUM(rim) AS rim_attempts, SUM(CASE WHEN rim = 1 THEN made ELSE 0 END) AS rim_makes
FROM shots WHERE opponent = 'SAS'
GROUP BY game_id, period, wembanyama;

-- Start a new stint at each full-five change, including within one guard group.
DROP VIEW IF EXISTS guard_stints;
CREATE VIEW guard_stints AS
WITH boundaries AS (
  SELECT *, CASE WHEN lineup = LAG(lineup) OVER (
      PARTITION BY gameid, period ORDER BY actionid) THEN 0 ELSE 1 END AS changed
  FROM events
), numbered AS (
  SELECT *, SUM(changed) OVER (
      PARTITION BY gameid, period ORDER BY actionid ROWS UNBOUNDED PRECEDING) AS stint
  FROM boundaries
)
SELECT gameid, period, stint, lineup, fox, castle, harper, wembanyama,
       MIN(actionid) AS first_action, MAX(actionid) AS last_action,
       SUM(elapsed) / 60.0 AS minutes
FROM numbered
GROUP BY gameid, period, stint, lineup, fox, castle, harper, wembanyama;
