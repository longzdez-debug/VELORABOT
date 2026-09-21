use crate::app::AppState;
use chrono::{Duration, Utc};
use sqlx::Row;
use tokio::time::{sleep, Duration as TokioDuration};

const SCAN_GRACE_SECS: i64 = 90;
const REMOVE_AFTER_STALE_SECS: i64 = 15 * 60;

pub async fn run(state: AppState) {
    loop {
        if let Err(e) = reconcile(&state).await {
            tracing::error!(error=%e, "listing lifecycle reconcile failed");
        }
        sleep(TokioDuration::from_secs(15)).await;
    }
}

async fn reconcile(state: &AppState) -> anyhow::Result<()> {
    let monitors = sqlx::query("SELECT id, interval_ms FROM monitors WHERE enabled=true")
        .fetch_all(&state.db).await?;
    let now = Utc::now();

    for m in monitors {
        let monitor_id: uuid::Uuid = m.try_get("id")?;
        let interval_ms: i64 = m.try_get("interval_ms")?;
        let grace = Duration::milliseconds(interval_ms.max(1000) * 4).max(Duration::seconds(SCAN_GRACE_SECS));
        let cutoff = now - grace;

        let recent_states = sqlx::query(
            "SELECT observed_kufar_ids FROM monitor_collector_state
             WHERE monitor_id=$1 AND last_success_at >= $2"
        ).bind(monitor_id).bind(cutoff).fetch_all(&state.db).await?;

        if recent_states.is_empty() { continue; }

        let mut observed = std::collections::HashSet::<String>::new();
        for row in recent_states {
            let ids: Vec<String> = row.try_get("observed_kufar_ids").unwrap_or_default();
            observed.extend(ids);
        }

        let rows = sqlx::query(
            "SELECT l.id,l.kufar_id,l.status,l.last_seen_at
             FROM listings l JOIN monitor_listings ml ON ml.listing_id=l.id
             WHERE ml.monitor_id=$1 AND l.status IN ('active','stale')"
        ).bind(monitor_id).fetch_all(&state.db).await?;

        for row in rows {
            let id: uuid::Uuid = row.try_get("id")?;
            let kufar_id: String = row.try_get("kufar_id")?;
            let status: String = row.try_get("status")?;
            let last_seen: chrono::DateTime<chrono::Utc> = row.try_get("last_seen_at")?;

            if observed.contains(&kufar_id) {
                if status != "active" {
                    transition(state, id, &status, "active", "collector_seen").await?;
                }
                continue;
            }

            if status == "active" {
                transition(state, id, "active", "stale", "missing_from_recent_successful_scan").await?;
            } else if status == "stale" && last_seen < now - Duration::seconds(REMOVE_AFTER_STALE_SECS) {
                transition(state, id, "stale", "removed", "missing_after_stale_grace").await?;
            }
        }
    }

    Ok(())
}

async fn transition(
    state: &AppState,
    listing_id: uuid::Uuid,
    from: &str,
    to: &str,
    reason: &str,
) -> anyhow::Result<()> {
    let mut tx = state.db.begin().await?;
    sqlx::query("UPDATE listings SET status=$2, stale_since=CASE WHEN $2='stale' THEN now() ELSE stale_since END, removed_at=CASE WHEN $2='removed' THEN now() ELSE removed_at END, updated_at=now() WHERE id=$1")
        .bind(listing_id).bind(to).execute(&mut *tx).await?;
    sqlx::query("INSERT INTO listing_status_history(listing_id,from_status,to_status,reason) VALUES($1,$2,$3,$4)")
        .bind(listing_id).bind(from).bind(to).bind(reason).execute(&mut *tx).await?;
    tx.commit().await?;
    Ok(())
}
