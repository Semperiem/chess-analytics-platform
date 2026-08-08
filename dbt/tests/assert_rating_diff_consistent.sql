-- Derived-column integrity: when both ratings are present, rating_diff must
-- equal player_rating - opponent_rating.
select game_key, player_rating, opponent_rating, rating_diff
from {{ ref('fct_games') }}
where opponent_rating is not null
  and rating_diff is not null
  and rating_diff <> (player_rating - opponent_rating)
