use anyhow::Result;
use sqlx::{PgPool, Row};
use uuid::Uuid;

pub async fn connect() -> Result<PgPool> {
    let url = std::env::var("DATABASE_URL")?;
    let pool = PgPool::connect(&url).await?;
    sqlx::migrate!("./migrations").run(&pool).await?;
    Ok(pool)
}

pub async fn create_user(pool: &PgPool, telegram_id: i64) -> Result<Uuid> {
    let row = sqlx::query(
        "INSERT INTO users (telegram_id) VALUES ($1)
         ON CONFLICT (telegram_id) DO UPDATE SET updated_at=now()
         RETURNING id"
    ).bind(telegram_id).fetch_one(pool).await?;
    Ok(row.try_get("id")?)
}
