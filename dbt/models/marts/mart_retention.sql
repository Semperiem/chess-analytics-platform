with cohort_sizes as (
    select cohort_month, count(distinct player_key) as cohort_size
    from {{ ref('fct_player_monthly_activity') }}
    where months_since_join = 0
    group by cohort_month
)
select a.cohort_month, cs.cohort_size, a.months_since_join,
       count(distinct a.player_key) as active_players,
       round(count(distinct a.player_key)::numeric / cs.cohort_size::numeric, 3) as retention_rate
from {{ ref('fct_player_monthly_activity') }} a
join cohort_sizes cs on cs.cohort_month = a.cohort_month
where a.months_since_join between 0 and 11 and cs.cohort_size >= 3
group by a.cohort_month, cs.cohort_size, a.months_since_join
