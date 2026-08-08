select player_key, username, name, title, country_code, followers, status, league,
       is_streamer, joined_date, joined_month, last_online_date, n_active_months
from {{ ref('stg_players') }}
