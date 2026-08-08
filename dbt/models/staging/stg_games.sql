select game_key, player_key, game_date, game_end_time, time_class_key, rated,
       player_color, player_rating, player_result, opponent_rating, result_bucket, rating_diff
from {{ source('chess','fact_games') }}
