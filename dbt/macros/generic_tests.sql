{% test not_in_future(model, column_name) %}
-- fails for any row whose date/timestamp is after today (data can't be from the future)
select {{ column_name }}
from {{ model }}
where {{ column_name }} > current_date
{% endtest %}
