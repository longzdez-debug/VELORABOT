use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Monitor {
    pub id: Uuid,
    pub user_id: Uuid,
    pub url: String,
    pub name: Option<String>,
    pub enabled: bool,
    pub interval_ms: i64,
    pub notify_new: bool,
    pub notify_price_drop: bool,
    pub notify_below_market: bool,
    pub min_drop_byn: f64,
    pub min_drop_percent: f64,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateMonitor {
    pub url: String,
    pub name: Option<String>,
    pub interval_ms: Option<i64>,
    pub notify_new: Option<bool>,
    pub notify_price_drop: Option<bool>,
    pub notify_below_market: Option<bool>,
    pub min_drop_byn: Option<f64>,
    pub min_drop_percent: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Listing {
    pub id: Uuid,
    pub kufar_id: String,
    pub url: String,
    pub title: String,
    pub description: Option<String>,
    pub price: Option<f64>,
    pub currency: String,
    pub location: Option<String>,
    pub images: Vec<String>,
    pub published_at: Option<DateTime<Utc>>,
    pub first_seen_at: DateTime<Utc>,
    pub last_seen_at: DateTime<Utc>,
    pub market_price: Option<f64>,
    pub market_confidence: Option<f64>,
    pub status: String,
    pub attributes: Value,
}

#[derive(Debug, Deserialize)]
pub struct IngestListing {
    pub monitor_id: Uuid,
    pub kufar_id: String,
    pub url: String,
    pub title: String,
    pub description: Option<String>,
    pub price: Option<f64>,
    pub currency: Option<String>,
    pub location: Option<String>,
    pub images: Option<Vec<String>>,
    pub published_at: Option<DateTime<Utc>>,
}
