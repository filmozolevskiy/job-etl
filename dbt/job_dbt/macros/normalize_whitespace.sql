{% macro normalize_ws(field) %}
    {#
        Normalize whitespace in a text field:
        - Trims leading and trailing whitespace
        - Collapses multiple consecutive spaces into a single space
        - Handles NULL values gracefully
        
        This is critical for the hash_key calculation to ensure
        "Acme Corp" and "Acme  Corp" (double space) are treated identically.
        
        Usage: {{ normalize_ws('company_name') }}
    #}
    REGEXP_REPLACE(TRIM({{ field }}), '\s+', ' ', 'g')
{% endmacro %}

