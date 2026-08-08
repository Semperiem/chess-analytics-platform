select date, year, quarter, month, month_name, day, day_of_week, day_name, is_weekend, month_start_date
from {{ source('chess','dim_date') }}
