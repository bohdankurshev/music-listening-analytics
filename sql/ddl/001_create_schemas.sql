CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;

COMMENT ON SCHEMA staging IS 'Raw-shaped data, one table per source';
COMMENT ON SCHEMA core IS 'Cleaned star schema for analysis and Power BI';