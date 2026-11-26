-- helper function
CREATE OR REPLACE FUNCTION core.normalize_name(t TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT regexp_replace(lower(trim(t)), '\s+', ' ', 'g')
$$;