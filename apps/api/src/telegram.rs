use crate::{app::AppState, models::Listing};
use anyhow::Result;
use teloxide::{prelude::*, types::{ChatId, InputFile, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup, Message, InputMediaPhoto, InputMedia}};
use url::Url;

pub async fn run(_state: AppState) -> Result<()> {
    let token = std::env::var("TELEGRAM_BOT_TOKEN")?;
    let bot = Bot::new(token);
    teloxide::repl(bot, |bot: Bot, msg: Message| async move {
        if let Some(text) = msg.text() {
            if text.starts_with("/start") {
                let url = std::env::var("MINIAPP_URL").unwrap_or_default();
                let keyboard = InlineKeyboardMarkup::new(vec![vec![InlineKeyboardButton::url("⚡ Открыть VELORA", url.parse()?)]]);

                bot.send_message(msg.chat.id, "VELORA\n\nМониторинг работает через Mini App.")
                    .reply_markup(keyboard)
                    .await?;
            }
        }
        respond(())
    }).await;
    Ok(())
}

fn esc(value: &str) -> String {
    value.replace("&","&amp;")
        .replace("<","&lt;")
        .replace(">","&gt;")
        .replace("\"","&quot;")
}

fn build_text(listing: &Listing, kind: &str, old_price: Option<f64>) -> String {
    let mut text = if kind == "price_drop" {
        let old = old_price.unwrap_or(0.0);
        let new = listing.price.unwrap_or(0.0);
        let d = old - new;
        let pct = if old > 0.0 { d / old * 100.0 } else { 0.0 };
        format!("📉 <b>СНИЖЕНИЕ ЦЕНЫ</b>\n\n<b>{}</b>\n\n<b>{:.0} → {:.0} BYN</b>\n🔻 {:.0} BYN (-{:.1}%)",
            esc(&listing.title), old, new, d, pct)
    } else {
        format!("🚨 <b>НОВОЕ ОБЪЯВЛЕНИЕ</b>\n\n<b>{}</b>\n\n💰 <b>{:.0} {}</b>",
            esc(&listing.title), listing.price.unwrap_or(0.0), esc(&listing.currency))
    };

    if let Some(market) = listing.market_price {
        let price = listing.price.unwrap_or(market);
        let diff = price - market;
        let pct = if market > 0.0 { diff / market * 100.0 } else { 0.0 };
        let label = if diff < 0.0 { "🟢 НИЖЕ РЫНКА" }
            else if diff > 0.0 { "🔴 ВЫШЕ РЫНКА" }
            else { "🟡 НА УРОВНЕ РЫНКА" };
        text.push_str(&format!("\n\n📊 Рыночная стоимость: <b>{:.0} BYN</b>\n{}\nНа {:.0} BYN ({:.1}%)",
            market, label, diff.abs(), pct.abs()));
    }

    if let Some(location) = &listing.location {
        text.push_str(&format!("\n\n📍 {}", esc(location)));
    }
    if let Some(description) = &listing.description {
        let short: String = description.chars().take(700).collect();
        text.push_str(&format!("\n\n📝 <b>Описание</b>\n{}", esc(&short)));
    }
    text.push_str(&format!("\n\n🔗 <a href=\"{}\">Открыть объявление</a>", esc(&listing.url)));
    text
}

pub async fn notify(chat_id: i64, listing: &Listing, kind: &str, old_price: Option<f64>) -> Result<Message> {
    let bot = Bot::new(std::env::var("TELEGRAM_BOT_TOKEN")?);
    let recipient = ChatId(chat_id);
    let mut text = build_text(listing, kind, old_price);

    if text.chars().count() > 1000 {
        text = text.chars().take(997).collect::<String>() + "...";
    }

    let images: Vec<Url> = listing.images.iter()
        .filter_map(|s| s.parse::<Url>().ok())
        .take(10)
        .collect();

    if images.is_empty() {
        return Ok(bot.send_message(recipient, text)
            .parse_mode(ParseMode::Html)
            .await?);
    }

    let media: Vec<InputMedia> = images.into_iter().enumerate().map(|(i, url)| {
        let mut photo = InputMediaPhoto::new(InputFile::url(url));
        if i == 0 {
            photo = photo.caption(text.clone()).parse_mode(ParseMode::Html);
        }
        InputMedia::Photo(photo)
    }).collect();

    let messages = bot.send_media_group(recipient, media).await?;
    messages.into_iter().next()
        .ok_or_else(|| anyhow::anyhow!("Telegram returned empty media group"))
}

pub async fn retry_pending(state: AppState) {
    loop {
        match retry_once(&state).await {
            Ok(count) if count > 0 => tracing::info!(count, "notification retry worker processed pending notifications"),
            Ok(_) => {}
            Err(error) => tracing::error!(%error, "notification retry worker failed"),
        }
        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
    }
}

async fn retry_once(state: &AppState) -> Result<u64> {
    use redis::AsyncCommands;
    use sqlx::Row;

    let mut redis = state.redis.get_multiplexed_async_connection().await?;
    let rows = sqlx::query(
        "SELECT n.id,n.user_id,n.monitor_id,n.listing_id,n.kind,n.attempts,u.telegram_id,
                l.id,l.kufar_id,l.url,l.title,l.description,l.price,l.currency,l.location,l.images,
                l.published_at,l.first_seen_at,l.last_seen_at,l.market_price,l.market_confidence,l.status,
                ph.price AS previous_price
         FROM notifications n
         JOIN users u ON u.id=n.user_id
         JOIN listings l ON l.id=n.listing_id
         LEFT JOIN LATERAL (
             SELECT price FROM price_history
             WHERE listing_id=l.id ORDER BY observed_at DESC OFFSET 1 LIMIT 1
         ) ph ON true
         WHERE n.status='pending' AND n.next_attempt_at <= now()
         ORDER BY n.id
         LIMIT 20"
    ).fetch_all(&state.db).await?;

    let mut processed = 0u64;
    for row in rows {
        let id: i64 = row.try_get("id")?;
        let lock_key = format!("velora:notification:{}", id);
        let claimed: bool = redis.set_nx(&lock_key, "1").await.unwrap_or(false);
        if !claimed { continue; }
        let _: bool = redis.expire(&lock_key, 30).await.unwrap_or(false);

        let listing = Listing {
            id: row.try_get("id")?,
            kufar_id: row.try_get("kufar_id")?,
            url: row.try_get("url")?,
            title: row.try_get("title")?,
            description: row.try_get("description")?,
            price: row.try_get("price")?,
            currency: row.try_get("currency")?,
            location: row.try_get("location")?,
            images: row.try_get("images")?,
            published_at: row.try_get("published_at")?,
            first_seen_at: row.try_get("first_seen_at")?,
            last_seen_at: row.try_get("last_seen_at")?,
            market_price: row.try_get("market_price")?,
            market_confidence: row.try_get("market_confidence")?,
            status: row.try_get("status")?,
        };
        let chat_id: i64 = row.try_get("telegram_id")?;
        let kind: String = row.try_get("kind")?;
        let old_price: Option<f64> = row.try_get("previous_price")?;

        match notify(chat_id, &listing, &kind, old_price).await {
            Ok(message) => {
                sqlx::query("UPDATE notifications SET status='sent',sent_at=now(),telegram_message_id=$2,last_error=NULL WHERE id=$1")
                    .bind(id).bind(i64::from(message.id.0)).execute(&state.db).await?;
                processed += 1;
            }
            Err(error) => {
                let attempts: i32 = row.try_get("attempts")?;
                let next_seconds = (2_i64.pow(attempts.min(8) as u32)).min(300);
                sqlx::query("UPDATE notifications SET attempts=attempts+1,last_error=$2,next_attempt_at=now()+make_interval(secs => $3) WHERE id=$1")
                    .bind(id).bind(error.to_string()).bind(next_seconds as f64).execute(&state.db).await?;
            }
        }
    }
    Ok(processed)
}
