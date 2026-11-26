SELECT 
CASE 
WHEN device_name = 'Android' THEN 'Phone'
WHEN device_name IN ('Windows', 'Web Player') THEN 'PC'
ELSE 'Other'
END AS platform_category,
COUNT(*) AS plays,
ROUND(SUM(ms_played) / 3600000.0, 1) AS hours,
ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_plays
FROM staging.stg_spotify_streams
WHERE ms_played > 0 /*існують записи з нульовим значенням ms_played, які потрібно виключити*/
GROUP BY platform_category
ORDER BY plays DESC;