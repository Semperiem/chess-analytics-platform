-- Cross-model integrity: the daily mart must equal the fact grain exactly.
with fact as (
    select game_date, count(*) as n_fact
    from {{ ref('fct_games') }}
    group by game_date
)
select d.game_date, d.games_played, f.n_fact
from {{ ref('mart_daily_games') }} d
full outer join fact f using (game_date)
where coalesce(d.games_played, -1) <> coalesce(f.n_fact, -1)
