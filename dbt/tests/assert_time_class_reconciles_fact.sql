-- The sum of games across time classes must equal the total game count.
select
    (select sum(games) from {{ ref('mart_time_class_performance') }}) as mart_total,
    (select count(*)   from {{ ref('fct_games') }})                   as fact_total
having (select sum(games) from {{ ref('mart_time_class_performance') }})
     <> (select count(*)  from {{ ref('fct_games') }})
