use sqlx::PgPool;

pub async fn estimate(pool: &PgPool, title: &str) -> (Option<f64>, Option<f64>) {
    let key = title.split_whitespace().find(|x| x.len() >= 3)
        .unwrap_or(title).to_lowercase();
    let mut values = sqlx::query_scalar::<_, f64>(
        "SELECT price FROM listings
         WHERE price IS NOT NULL AND price > 0 AND status='active'
         AND lower(title) LIKE '%' || $1 || '%' LIMIT 100"
    ).bind(key).fetch_all(pool).await.unwrap_or_default();

    if values.len() < 5 { return (None, None); }
    values.sort_by(|a,b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let median = values[values.len()/2];
    let confidence = (values.len() as f64 / 30.0).min(1.0);
    (Some(median), Some(confidence))
}
