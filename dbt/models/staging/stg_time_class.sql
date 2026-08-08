select time_class_key, time_class, rules, speed_rank
from {{ source('chess','dim_time_class') }}
