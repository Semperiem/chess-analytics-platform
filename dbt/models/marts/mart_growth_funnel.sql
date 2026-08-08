with flags as (
    select player_key, cohort_month,
           bool_or(months_since_join = 0) as activated_month0,
           bool_or(months_since_join between 1 and 3) as active_by_month3,
           bool_or(months_since_join between 1 and 6) as active_by_month6
    from {{ ref('fct_player_monthly_activity') }}
    group by player_key, cohort_month
)
select cohort_month,
       count(*) as players_joined,
       count(*) filter (where activated_month0) as activated_month0,
       count(*) filter (where active_by_month3) as active_by_month3,
       count(*) filter (where active_by_month6) as active_by_month6,
       round(count(*) filter (where active_by_month3)::numeric / count(*)::numeric, 3) as pct_active_by_month3,
       round(count(*) filter (where active_by_month6)::numeric / count(*)::numeric, 3) as pct_retained_month6
from flags
group by cohort_month
