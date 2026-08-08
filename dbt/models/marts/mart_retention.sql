with cohort_sizes as (
    -- true cohort population: every distinct player who joined in this month,
    -- across ALL their activity — not just those active in month 0. Using the
    -- month-0-only count as the denominator lets later-month re-activations
    -- push retention above 100%, which is wrong. (Caught by the accepted_range
    -- [0,1] test on retention_rate.)
    select cohort_month, count(distinct player_key) as cohort_size
    from {{ ref('fct_player_monthly_activity') }}
    group by cohort_month
)
select a.cohort_month, cs.cohort_size, a.months_since_join,
       count(distinct a.player_key) as active_players,
       round(count(distinct a.player_key)::numeric / cs.cohort_size::numeric, 3) as retention_rate
from {{ ref('fct_player_monthly_activity') }} a
join cohort_sizes cs on cs.cohort_month = a.cohort_month
where a.months_since_join between 0 and 11 and cs.cohort_size >= 3
group by a.cohort_month, cs.cohort_size, a.months_since_join
