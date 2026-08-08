select player_key, activity_month, cohort_month, months_since_join, is_active
from {{ ref('stg_monthly_activity') }}
