use crate::{db, market, models::*, telegram};
use axum::{extract::{Path, State}, http::{HeaderMap, StatusCode}, routing::{get, post, delete}, Json, Router};
use chrono::Utc;
use hmac::{Hmac, Mac};
use serde::Deserialize;
use sha2::Sha256;
use subtle::ConstantTimeEq;
use urlencoding;
use redis::AsyncCommands;
use sqlx::PgPool;
use std::{env, collections::hash_map::DefaultHasher, hash::{Hash, Hasher}};
use tower_http::{cors::CorsLayer, trace::TraceLayer};
use uuid::Uuid;

#[derive(Clone)]
pub struct AppState { pub db: PgPool, pub redis: redis::Client }

impl AppState {
    pub async fn new() -> anyhow::Result<Self> {
        Ok(Self {
            db: db::connect().await?,
            redis: redis::Client::open(env::var("REDIS_URL")?)?
        })
    }
}

#[derive(Deserialize)]
struct TgUser { id: i64 }

fn user_id(headers: &HeaderMap) -> Result<i64, StatusCode> {
    let init = headers.get("x-telegram-init-data").and_then(|v| v.to_str().ok()).ok_or(StatusCode::UNAUTHORIZED)?;
    let mut parts: Vec<(&str,&str)> = init.split('&').filter_map(|p| { let mut i=p.splitn(2,'='); Some((i.next()?,i.next().unwrap_or(""))) }).collect();
    let hash = parts.iter().find(|(k,_)| *k=="hash").map(|(_,v)| *v).ok_or(StatusCode::UNAUTHORIZED)?;
    parts.retain(|(k,_)| *k!="hash");
    parts.sort_by(|a,b| a.0.cmp(b.0));
    let check = parts.iter().map(|(k,v)| format!("{}={}",k,v)).collect::<Vec<_>>().join("\n");
    type H = Hmac<Sha256>;
    let token = std::env::var("TELEGRAM_BOT_TOKEN").map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let mut key = H::new_from_slice(b"WebAppData").map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    key.update(token.as_bytes());
    let secret = key.finalize().into_bytes();
    let mut mac = H::new_from_slice(&secret).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    mac.update(check.as_bytes());
    let expected = mac.finalize().into_bytes().iter().map(|b| format!("{:02x}", b)).collect::<String>();
    if expected.as_bytes().ct_eq(hash.as_bytes()).unwrap_u8()!=1 { return Err(StatusCode::UNAUTHORIZED); }
    let raw = parts.iter().find(|(k,_)| *k=="user").map(|(_,v)| *v).ok_or(StatusCode::UNAUTHORIZED)?;
    let decoded = urlencoding::decode(raw).map_err(|_| StatusCode::UNAUTHORIZED)?;
    let user: TgUser = serde_json::from_str(&decoded).map_err(|_| StatusCode::UNAUTHORIZED)?;
    Ok(user.id)
}

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/api/monitors", get(list_monitors).post(create_monitor))
        .route("/api/monitors/{id}", delete(delete_monitor).put(update_monitor))
        .route("/api/listings", get(list_listings))
        .route("/api/collector/monitors", get(collector_monitors))
        .route("/api/ingest/listing", post(ingest_listing))
        .with_state(state)
        .layer(CorsLayer::permissive())
        .layer(TraceLayer::new_for_http())
}

async fn health() -> &'static str { "ok" }

async fn list_monitors(State(s): State<AppState>, headers: HeaderMap) -> Result<Json<Vec<Monitor>>, StatusCode> {
    let uid = user_id(&headers)?;
    let user = db::create_user(&s.db, uid).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let rows = sqlx::query_as::<_, MonitorRow>("SELECT id,user_id,url,name,enabled,interval_ms,notify_new,notify_price_drop,notify_below_market,min_drop_byn,min_drop_percent,created_at FROM monitors WHERE user_id=$1 ORDER BY created_at DESC").bind(user).fetch_all(&s.db).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(rows.into_iter().map(Into::into).collect()))
}

async fn create_monitor(State(s): State<AppState>, headers: HeaderMap, Json(input): Json<CreateMonitor>) -> Result<Json<Monitor>, StatusCode> {
    let uid = user_id(&headers)?;
    let user = db::create_user(&s.db, uid).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let id = Uuid::new_v4();
    let row = sqlx::query_as::<_, MonitorRow>("INSERT INTO monitors (id,user_id,url,name,enabled,interval_ms,notify_new,notify_price_drop,notify_below_market,min_drop_byn,min_drop_percent) VALUES ($1,$2,$3,$4,true,$5,$6,$7,$8,$9,$10) RETURNING id,user_id,url,name,enabled,interval_ms,notify_new,notify_price_drop,notify_below_market,min_drop_byn,min_drop_percent,created_at")
        .bind(id).bind(user).bind(input.url).bind(input.name).bind(input.interval_ms.unwrap_or(1500).clamp(1000,60000))
        .bind(input.notify_new.unwrap_or(true)).bind(input.notify_price_drop.unwrap_or(true)).bind(input.notify_below_market.unwrap_or(true))
        .bind(input.min_drop_byn.unwrap_or(50.0)).bind(input.min_drop_percent.unwrap_or(3.0))
        .fetch_one(&s.db).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(row.into()))
}

async fn delete_monitor(State(s): State<AppState>, headers: HeaderMap, Path(id): Path<Uuid>) -> Result<StatusCode, StatusCode> {
    let uid = user_id(&headers)?;
    let user = db::create_user(&s.db, uid).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    sqlx::query("DELETE FROM monitors WHERE id=$1 AND user_id=$2").bind(id).bind(user).execute(&s.db).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(StatusCode::NO_CONTENT)
}

#[derive(Deserialize)]
struct UpdateMonitor {
    enabled: Option<bool>,
    interval_ms: Option<i64>,
    notify_new: Option<bool>,
    notify_price_drop: Option<bool>,
    notify_below_market: Option<bool>,
    min_drop_byn: Option<f64>,
    min_drop_percent: Option<f64>,
}

async fn update_monitor(State(s): State<AppState>, headers: HeaderMap, Path(id): Path<Uuid>, Json(input): Json<UpdateMonitor>) -> Result<Json<Monitor>, StatusCode> {
    let uid = user_id(&headers)?;
    let user = db::create_user(&s.db, uid).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let row = sqlx::query_as::<_, MonitorRow>(
        "UPDATE monitors SET enabled=COALESCE($3,enabled), interval_ms=COALESCE($4,interval_ms), notify_new=COALESCE($5,notify_new), notify_price_drop=COALESCE($6,notify_price_drop), notify_below_market=COALESCE($7,notify_below_market), min_drop_byn=COALESCE($8,min_drop_byn), min_drop_percent=COALESCE($9,min_drop_percent) WHERE id=$1 AND user_id=$2 RETURNING id,user_id,url,name,enabled,interval_ms,notify_new,notify_price_drop,notify_below_market,min_drop_byn,min_drop_percent,created_at")
        .bind(id).bind(user).bind(input.enabled).bind(input.interval_ms.map(|v| v.clamp(1000,60000))).bind(input.notify_new).bind(input.notify_price_drop).bind(input.notify_below_market).bind(input.min_drop_byn.map(|v| v.max(0.0))).bind(input.min_drop_percent.map(|v| v.max(0.0))).fetch_optional(&s.db).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(row.into()))
}

async fn list_listings(State(s): State<AppState>, headers: HeaderMap) -> Result<Json<Vec<Listing>>, StatusCode> {
    let uid = user_id(&headers)?;
    let user = db::create_user(&s.db, uid).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let rows = sqlx::query_as::<_, ListingRow>("SELECT DISTINCT l.id,l.kufar_id,l.url,l.title,l.description,l.price,l.currency,l.location,l.images,l.published_at,l.first_seen_at,l.last_seen_at,l.market_price,l.market_confidence,l.status,l.attributes FROM listings l JOIN monitor_listings ml ON ml.listing_id=l.id JOIN monitors m ON m.id=ml.monitor_id WHERE m.user_id=$1 ORDER BY l.first_seen_at DESC LIMIT 200").bind(user).fetch_all(&s.db).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(rows.into_iter().map(Into::into).collect()))
}

async fn collector_monitors(State(s): State<AppState>, headers: HeaderMap) -> Result<Json<Vec<Monitor>>, StatusCode> {
    let expected = std::env::var("COLLECTOR_TOKEN").map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let supplied = headers.get("x-collector-token").and_then(|v| v.to_str().ok()).unwrap_or_default();
    if supplied != expected { return Err(StatusCode::UNAUTHORIZED); }
    let rows = sqlx::query_as::<_, MonitorRow>("SELECT id,user_id,url,name,enabled,interval_ms,notify_new,notify_price_drop,notify_below_market,min_drop_byn,min_drop_percent,created_at FROM monitors WHERE enabled=true ORDER BY created_at").fetch_all(&s.db).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(rows.into_iter().map(Into::into).collect()))
}

async fn ingest_listing(State(s): State<AppState>, headers: HeaderMap, Json(input): Json<IngestListing>) -> Result<Json<Listing>, StatusCode> {
    let expected = std::env::var("COLLECTOR_TOKEN").map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let supplied = headers.get("x-collector-token").and_then(|v| v.to_str().ok()).unwrap_or_default();
    if supplied != expected { return Err(StatusCode::UNAUTHORIZED); }
    let mut redis = s.redis.get_multiplexed_async_connection().await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let fingerprint = { let mut h = DefaultHasher::new(); input.kufar_id.hash(&mut h); input.url.hash(&mut h); input.title.trim().to_lowercase().hash(&mut h); input.price.map(|v| (v * 100.0).round() as i64).hash(&mut h); format!("{:016x}", h.finish()) };
    let lock_key = format!("velora:lock:{}", input.kufar_id);
    let mut lock_acquired = false;
    for _ in 0..3 {
        lock_acquired = redis.set_nx(&lock_key, &fingerprint).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        if lock_acquired { break; }
        tokio::time::sleep(std::time::Duration::from_millis(75)).await;
    }
    if !lock_acquired {
        if let Some(row) = sqlx::query_as::<_, ListingRow>("SELECT id,kufar_id,url,title,description,price,currency,location,images,published_at,first_seen_at,last_seen_at,market_price,market_confidence,status,attributes FROM listings WHERE kufar_id=$1")
            .bind(&input.kufar_id).fetch_optional(&s.db).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)? {
            return Ok(Json(row.into()));
        }
    }
    let _: bool = redis.expire(&lock_key, 5).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let fingerprint_key = format!("velora:fingerprint:{}", fingerprint);
    let first_seen_claim: bool = redis.set_nx(&fingerprint_key, "1").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let _: bool = redis.expire(&fingerprint_key, 300).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if !first_seen_claim {
        if let Some(row) = sqlx::query_as::<_, ListingRow>("SELECT id,kufar_id,url,title,description,price,currency,location,images,published_at,first_seen_at,last_seen_at,market_price,market_confidence,status,attributes FROM listings WHERE kufar_id=$1")
            .bind(&input.kufar_id).fetch_optional(&s.db).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)? {
            return Ok(Json(row.into()));
        }
    }
    let previous = sqlx::query_scalar::<_, f64>("SELECT price FROM listings WHERE kufar_id=$1").bind(&input.kufar_id).fetch_optional(&s.db).await.ok().flatten();
    let existed = sqlx::query_scalar::<_, bool>("SELECT EXISTS(SELECT 1 FROM listings WHERE kufar_id=$1)").bind(&input.kufar_id).fetch_one(&s.db).await.unwrap_or(false);
    let id = Uuid::new_v4();
    let now = Utc::now();
    let attributes = market::extract_attributes(&input.title, input.description.as_deref());
    let row = sqlx::query_as::<_, ListingRow>("INSERT INTO listings (id,kufar_id,url,title,description,price,currency,location,images,published_at,first_seen_at,last_seen_at,attributes,status) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$11,$12,'active') ON CONFLICT(kufar_id) DO UPDATE SET title=EXCLUDED.title,description=COALESCE(EXCLUDED.description,listings.description),price=EXCLUDED.price,location=COALESCE(EXCLUDED.location,listings.location),images=CASE WHEN cardinality(EXCLUDED.images)>0 THEN EXCLUDED.images ELSE listings.images END,last_seen_at=now(),updated_at=now() RETURNING id,kufar_id,url,title,description,price,currency,location,images,published_at,first_seen_at,last_seen_at,market_price,market_confidence,status,attributes")
        .bind(id).bind(&input.kufar_id).bind(&input.url).bind(&input.title).bind(&input.description).bind(input.price).bind(input.currency.unwrap_or("BYN".into())).bind(&input.location).bind(input.images.unwrap_or_default()) .bind(input.published_at).bind(now).bind(&attributes)
        .fetch_one(&s.db).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    sqlx::query("INSERT INTO monitor_listings(monitor_id,listing_id) VALUES($1,$2) ON CONFLICT DO NOTHING").bind(input.monitor_id).bind(row.id).execute(&s.db).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if let Some(p) = input.price {
        if previous.map(|old| (old - p).abs() > f64::EPSILON).unwrap_or(true) {
            sqlx::query("INSERT INTO price_history(listing_id,price) VALUES($1,$2)").bind(row.id).bind(p).execute(&s.db).await.ok();
        }
    }
    if !existed { sqlx::query("UPDATE listings SET first_detected_at=$2 WHERE id=$1").bind(row.id).bind(now).execute(&s.db).await.ok(); }
    let (market_price, confidence) = market::estimate(&s.db, &row.title, row.description.as_deref(), Some(row.id)).await;
    sqlx::query("UPDATE listings SET market_price=$2,market_confidence=$3 WHERE id=$1").bind(row.id).bind(market_price).bind(confidence).execute(&s.db).await.ok();
    let mut out: Listing = row.into();
    out.market_price = market_price; out.market_confidence = confidence;

    let monitor = sqlx::query_as::<_, MonitorRow>("SELECT id,user_id,url,name,enabled,interval_ms,notify_new,notify_price_drop,notify_below_market,min_drop_byn,min_drop_percent,created_at FROM monitors WHERE id=$1").bind(input.monitor_id).fetch_optional(&s.db).await.ok().flatten();
    if let Some(m) = monitor {
        let chat_id = sqlx::query_scalar::<_, i64>("SELECT telegram_id FROM users WHERE id=$1").bind(m.user_id).fetch_optional(&s.db).await.ok().flatten();
        if let Some(chat) = chat_id {
            let new_price = input.price.unwrap_or(0.0);
            let old_price = previous.unwrap_or(new_price);
            let drop_byn = old_price - new_price;
            let drop_pct = if old_price > 0.0 { drop_byn / old_price * 100.0 } else { 0.0 };
            let below_market = out.market_price.map(|market| new_price < market).unwrap_or(false);
            let drop_ok = drop_byn >= m.min_drop_byn || drop_pct >= m.min_drop_percent;
            let kind = if existed && previous.is_some() && drop_byn > 0.0 && m.notify_price_drop && drop_ok { "price_drop" }
                else if !existed && m.notify_new { "new" }
                else if !existed && m.notify_below_market && below_market { "new" }
                else { "" };
            if !kind.is_empty() {
                let inserted = sqlx::query_scalar::<_, i64>("INSERT INTO notifications(user_id,monitor_id,listing_id,kind) VALUES($1,$2,$3,$4) ON CONFLICT(user_id,listing_id,kind) DO NOTHING RETURNING id")
                    .bind(m.user_id).bind(m.id).bind(out.id).bind(kind).fetch_optional(&s.db).await.ok().flatten().is_some();
                if inserted {
                    let send_started = Utc::now();
                    if let Ok(message) = telegram::notify(chat, &out, kind, previous).await {
                        let sent_at = Utc::now();
                        let detected_at = sqlx::query_scalar::<_, chrono::DateTime<Utc>>("SELECT COALESCE(first_detected_at, first_seen_at) FROM listings WHERE id=$1").bind(out.id).fetch_one(&s.db).await.unwrap_or(out.first_seen_at);
                        let detection_ms = detected_at.signed_duration_since(out.published_at.unwrap_or(detected_at)).num_milliseconds().max(0);
                        let delivery_ms = sent_at.signed_duration_since(send_started).num_milliseconds().max(0);
                        let total_ms = sent_at.signed_duration_since(out.published_at.unwrap_or(out.first_seen_at)).num_milliseconds().max(0);
                        sqlx::query("UPDATE notifications SET status='sent',sent_at=$2,telegram_message_id=$3,detection_latency_ms=$4,delivery_latency_ms=$5,total_latency_ms=$6,last_error=NULL WHERE user_id=$1 AND listing_id=$7 AND kind=$8")
                            .bind(m.user_id).bind(sent_at).bind(i64::from(message.id.0)).bind(detection_ms).bind(delivery_ms).bind(total_ms).bind(out.id).bind(kind).execute(&s.db).await.ok();
                        sqlx::query("UPDATE listings SET telegram_sent_at=$2,detection_latency_ms=$3,delivery_latency_ms=$4,total_latency_ms=$5 WHERE id=$1")
                            .bind(out.id).bind(sent_at).bind(detection_ms).bind(delivery_ms).bind(total_ms).execute(&s.db).await.ok();
                    }
                }
            }
        }
    }
    Ok(Json(out))
}

#[derive(sqlx::FromRow)]
struct MonitorRow { id:Uuid,user_id:Uuid,url:String,name:Option<String>,enabled:bool,interval_ms:i64,notify_new:bool,notify_price_drop:bool,notify_below_market:bool,min_drop_byn:f64,min_drop_percent:f64,created_at:chrono::DateTime<Utc> }
impl From<MonitorRow> for Monitor { fn from(x:MonitorRow)->Self { Self{id:x.id,user_id:x.user_id,url:x.url,name:x.name,enabled:x.enabled,interval_ms:x.interval_ms,notify_new:x.notify_new,notify_price_drop:x.notify_price_drop,notify_below_market:x.notify_below_market,min_drop_byn:x.min_drop_byn,min_drop_percent:x.min_drop_percent,created_at:x.created_at} } }

#[derive(sqlx::FromRow)]
struct ListingRow { id:Uuid,kufar_id:String,url:String,title:String,description:Option<String>,price:Option<f64>,currency:String,location:Option<String>,images:Vec<String>,published_at:Option<chrono::DateTime<Utc>>,first_seen_at:chrono::DateTime<Utc>,last_seen_at:chrono::DateTime<Utc>,market_price:Option<f64>,market_confidence:Option<f64>,status:String,attributes:serde_json::Value }
impl From<ListingRow> for Listing { fn from(x:ListingRow)->Self { Self{id:x.id,kufar_id:x.kufar_id,url:x.url,title:x.title,description:x.description,price:x.price,currency:x.currency,location:x.location,images:x.images,published_at:x.published_at,first_seen_at:x.first_seen_at,last_seen_at:x.last_seen_at,market_price:x.market_price,market_confidence:x.market_confidence,status:x.status,attributes:x.attributes} } }
