select player_key, activity_month, cohort_month, months_since_join, is_active
from {{ source('chess','fact_player_monthly_activity') }}
