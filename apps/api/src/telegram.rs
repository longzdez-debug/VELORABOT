use crate::{app::AppState, models::Listing};
use anyhow::Result;
use teloxide::{prelude::*, types::{InputFile, ParseMode}};

pub async fn run(_state: AppState) -> Result<()> {
    let token = std::env::var("TELEGRAM_BOT_TOKEN")?;
    let bot = Bot::new(token);
    teloxide::repl(bot, |bot: Bot, msg: Message| async move {
        if let Some(text) = msg.text() {
            if text.starts_with("/start") {
                let url = std::env::var("MINIAPP_URL").unwrap_or_default();
                bot.send_message(msg.chat.id, format!("VELORA\n\nНастройки находятся в Mini App.\n{}", url)).await?;
            }
        }
        respond(())
    }).await?;
    Ok(())
}

pub async fn notify(chat_id: i64, listing: &Listing, kind: &str, old_price: Option<f64>) -> Result<()> {
    let bot = Bot::new(std::env::var("TELEGRAM_BOT_TOKEN")?);
    let mut text = if kind == "price_drop" {
        let old = old_price.unwrap_or(0.0);
        let new = listing.price.unwrap_or(0.0);
        let d = old - new;
        let pct = if old > 0.0 { d / old * 100.0 } else { 0.0 };
        format!("📉 <b>СНИЖЕНИЕ ЦЕНЫ</b>\n\n<b>{}</b>\n\n<b>{:.0} → {:.0} BYN</b>\n🔻 {:.0} BYN (-{:.1}%)", listing.title, old, new, d, pct)
    } else {
        format!("🚨 <b>НОВОЕ ОБЪЯВЛЕНИЕ</b>\n\n<b>{}</b>\n\n💰 <b>{:.0} {}</b>", listing.title, listing.price.unwrap_or(0.0), listing.currency)
    };
    if let Some(market) = listing.market_price {
        let price = listing.price.unwrap_or(market);
        let diff = price - market;
        let pct = if market > 0.0 { diff / market * 100.0 } else { 0.0 };
        let label = if diff < 0.0 { "🟢 НИЖЕ РЫНКА" } else if diff > 0.0 { "🔴 ВЫШЕ РЫНКА" } else { "🟡 НА УРОВНЕ РЫНКА" };
        text.push_str(&format!("\n\n📊 Рыночная стоимость: <b>{:.0} BYN</b>\n{}\nНа {:.0} BYN ({:.1}%)", market, label, diff.abs(), pct.abs()));
    }
    if let Some(location) = &listing.location { text.push_str(&format!("\n\n📍 {}", location)); }
    if let Some(description) = &listing.description {
        let short: String = description.chars().take(700).collect();
        text.push_str(&format!("\n\n📝 <b>Описание</b>\n{}", short));
    }
    text.push_str(&format!("\n\n🔗 <a href=\"{}\">Открыть объявление</a>", listing.url));

    if let Some(image) = listing.images.first() {
        bot.send_photo(chat_id, InputFile::url(image.clone())).caption(text).parse_mode(ParseMode::Html).await?;
    } else {
        bot.send_message(chat_id, text).parse_mode(ParseMode::Html).await?;
    }
    Ok(())
}
