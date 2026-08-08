select tc.time_class, tc.rules,
       count(*) as games,
       round(avg((g.result_bucket = 'win')::int), 3) as win_rate,
       round(avg(g.player_rating), 0) as avg_player_rating
from {{ ref('fct_games') }} g
join {{ ref('dim_time_class') }} tc on tc.time_class_key = g.time_class_key
group by tc.time_class, tc.rules
