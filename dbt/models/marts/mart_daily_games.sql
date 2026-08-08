select game_date,
       count(*) as games_played,
       count(distinct player_key) as distinct_players,
       round(avg((result_bucket = 'win')::int), 3) as win_rate
from {{ ref('fct_games') }}
group by game_date
