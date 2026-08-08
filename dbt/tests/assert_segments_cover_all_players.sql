-- Cross-model completeness: mart_player_segments and dim_players must cover the
-- exact same set of players (no orphans, no missing).
select coalesce(s.player_key, p.player_key) as player_key
from {{ ref('mart_player_segments') }} s
full outer join {{ ref('dim_players') }} p using (player_key)
where s.player_key is null or p.player_key is null
