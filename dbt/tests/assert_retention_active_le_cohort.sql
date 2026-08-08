-- Core cohort invariant: at any offset, the number of active players can never
-- exceed the cohort's total size, so retention is bounded by 100%. This is the
-- exact property that failed before mart_retention's denominator was fixed to
-- the full cohort population.
select cohort_month, months_since_join, active_players, cohort_size
from {{ ref('mart_retention') }}
where active_players > cohort_size
