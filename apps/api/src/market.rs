use chrono::{DateTime, Utc};
use sqlx::PgPool;
use std::collections::HashSet;

#[derive(sqlx::FromRow)]
struct Candidate {
    title: String,
    price: f64,
    first_seen_at: DateTime<Utc>,
}

fn tokens(title: &str) -> HashSet<String> {
    title
        .to_lowercase()
        .split(|c: char| !c.is_alphanumeric())
        .filter(|s| s.len() >= 2)
        .filter(|s| !matches!(*s, "для" | "и" | "в" | "на" | "с" | "из" | "по" | "the" | "for"))
        .map(ToOwned::to_owned)
        .collect()
}

fn weighted_median(values: &mut [(f64, f64)]) -> Option<f64> {
    if values.is_empty() { return None; }
    values.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
    let total: f64 = values.iter().map(|(_, w)| *w).sum();
    if total <= 0.0 { return None; }
    let mut acc = 0.0;
    for (value, weight) in values.iter() {
        acc += *weight;
        if acc >= total / 2.0 { return Some(*value); }
    }
    values.last().map(|x| x.0)
}

pub async fn estimate(pool: &PgPool, title: &str, exclude_id: Option<uuid::Uuid>) -> (Option<f64>, Option<f64>) {
    let wanted = tokens(title);
    if wanted.is_empty() { return (None, None); }
    let cache_key = format!("market:{}", { let mut v: Vec<_> = wanted.iter().cloned().collect(); v.sort(); v.join("|") });
    if let Ok(url) = std::env::var("REDIS_URL") {
        if let Ok(client) = redis::Client::open(url) {
            if let Ok(mut conn) = client.get_multiplexed_async_connection().await {
                if let Ok(Some(raw)) = redis::AsyncCommands::get::<_, Option<String>>(&mut conn, &cache_key).await {
                    let mut p = raw.split(':');
                    if let (Some(a), Some(b)) = (p.next(), p.next()) { if let (Ok(price), Ok(conf)) = (a.parse::<f64>(), b.parse::<f64>()) { return (Some(price), Some(conf)); } }
                }
            }
        }
    }

    let rows = sqlx::query_as::<_, Candidate>(
        "SELECT title, price, first_seen_at FROM listings
         WHERE price IS NOT NULL AND price > 0 AND status='active'
           AND ($1::uuid IS NULL OR id <> $1)
         ORDER BY first_seen_at DESC LIMIT 1000"
    ).bind(exclude_id).fetch_all(pool).await.unwrap_or_default();

    let now = Utc::now();
    let mut scored: Vec<(f64, f64)> = rows.into_iter().filter_map(|row| {
        let have = tokens(&row.title);
        let overlap = wanted.intersection(&have).count() as f64;
        let similarity = overlap / wanted.len().max(1) as f64;
        if overlap == 0.0 || similarity < 0.30 { return None; }
        let age_days = (now - row.first_seen_at).num_seconds().max(0) as f64 / 86_400.0;
        let recency = 1.0 / (1.0 + age_days / 14.0);
        let weight = (0.25 + similarity * 1.75) * recency;
        Some((row.price, weight))
    }).collect();

    if scored.len() < 5 { return (None, None); }

    scored.sort_by(|a,b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
    let q1 = scored[scored.len()/4].0;
    let q3 = scored[(scored.len()*3)/4].0;
    let iqr = (q3 - q1).max(0.0);
    let low = if iqr > 0.0 { q1 - 1.5 * iqr } else { q1 * 0.7 };
    let high = if iqr > 0.0 { q3 + 1.5 * iqr } else { q3 * 1.3 };
    let mut filtered: Vec<(f64, f64)> = scored.into_iter().filter(|(p, _)| *p >= low && *p <= high).collect();
    if filtered.len() < 5 { return (None, None); }

    let market = weighted_median(&mut filtered);
    let sample_factor = (filtered.len() as f64 / 25.0).min(1.0);
    let weight_total: f64 = filtered.iter().map(|(_, w)| *w).sum();
    let confidence = (sample_factor * (weight_total / 20.0).min(1.0)).clamp(0.0, 1.0);
    let result = (market, Some(confidence));
    if let (Some(price), Some(conf)) = result {
        if let Ok(url) = std::env::var("REDIS_URL") {
            if let Ok(client) = redis::Client::open(url) {
                if let Ok(mut conn) = client.get_multiplexed_async_connection().await {
                    let _: Result<(), _> = redis::AsyncCommands::set_ex(&mut conn, &cache_key, format!("{price}:{conf}"), 15).await;
                }
            }
        }
    }
    result
}
