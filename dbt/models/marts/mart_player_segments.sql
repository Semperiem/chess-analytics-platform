select player_key, username, title, country_code, status, n_active_months,
       date_part('year', age(current_date, joined_date)) * 12
         + date_part('month', age(current_date, joined_date)) as tenure_months,
       current_date - last_online_date as days_since_last_online,
       case when current_date - last_online_date <= 7 then 'active'
            when current_date - last_online_date <= 30 then 'lapsing'
            when current_date - last_online_date <= 90 then 'at_risk'
            else 'churned' end as recency_segment,
       case when title is null then 'untitled'
            when title in ('GM','IM') then 'top_title'
            else 'other_titled' end as title_tier,
       ntile(4) over (order by n_active_months) as engagement_quartile
from {{ ref('dim_players') }}
