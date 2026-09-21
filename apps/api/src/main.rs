mod app;
mod db;
mod market;
mod models;
mod telegram;

use anyhow::Result;
use dotenvy::dotenv;
use app::AppState;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .with(tracing_subscriber::fmt::layer())
        .init();

    let state = AppState::new().await?;
    let bot_state = state.clone();
    tokio::spawn(async move {
        if let Err(e) = telegram::run(bot_state).await {
            tracing::error!(error = %e, "telegram bot stopped");
        }
    });

    let retry_state = state.clone();
    tokio::spawn(async move {
        telegram::retry_pending(retry_state).await;
    });

    let app = app::router(state);
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await?;
    axum::serve(listener, app).await?;
    Ok(())
}
