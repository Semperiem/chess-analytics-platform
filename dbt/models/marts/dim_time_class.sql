select time_class_key, time_class, rules, speed_rank
from {{ ref('stg_time_class') }}
