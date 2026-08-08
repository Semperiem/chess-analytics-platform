select p.username, p.title,
       date_trunc('month', g.game_date)::date as game_month,
       tc.time_class,
       round(avg(g.player_rating), 0) as avg_rating,
       count(*) as games
from {{ ref('fct_games') }} g
join {{ ref('dim_players') }} p on p.player_key = g.player_key
join {{ ref('dim_time_class') }} tc on tc.time_class_key = g.time_class_key
group by p.username, p.title, date_trunc('month', g.game_date), tc.time_class
