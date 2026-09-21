use crate::{app::AppState, models::Listing};
use anyhow::Result;
use teloxide::{prelude::*, types::{ChatId, InputFile, ParseMode}};
use url::Url;

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
    }).await;
    Ok(())
}

fn esc(value: &str) -> String { value.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\"","&quot;") }\n\npub async fn notify(chat_id: i64, listing: &Listing, kind: &str, old_price: Option<f64>) -> Result<()> {
    let bot = Bot::new(std::env::var("TELEGRAM_BOT_TOKEN")?);
    let mut text = if kind == "price_drop" {
        let old = old_price.unwrap_or(0.0);
        let new = listing.price.unwrap_or(0.0);
        let d = old - new;
        let pct = if old > 0.0 { d / old * 100.0 } else { 0.0 };
        format!("📉 <b>СНИЖЕНИЕ ЦЕНЫ</b>\n\n<b>{}</b>\n\n<b>{:.0} → {:.0} BYN</b>\n🔻 {:.0} BYN (-{:.1}%)", esc(&listing.title), old, new, d, pct)
    } else {
        format!("🚨 <b>НОВОЕ ОБЪЯВЛЕНИЕ</b>\n\n<b>{}</b>\n\n💰 <b>{:.0} {}</b>", esc(&listing.title), listing.price.unwrap_or(0.0), esc(&listing.currency))
    };
    if let Some(market) = listing.market_price {
        let price = listing.price.unwrap_or(market);
        let diff = price - market;
        let pct = if market > 0.0 { diff / market * 100.0 } else { 0.0 };
        let label = if diff < 0.0 { "🟢 НИЖЕ РЫНКА" } else if diff > 0.0 { "🔴 ВЫШЕ РЫНКА" } else { "🟡 НА УРОВНЕ РЫНКА" };
        text.push_str(&format!("\n\n📊 Рыночная стоимость: <b>{:.0} BYN</b>\n{}\nНа {:.0} BYN ({:.1}%)", market, label, diff.abs(), pct.abs()));
    }
    if let Some(location) = &listing.location { text.push_str(&format!("\n\n📍 {}", esc(location))); }
    if let Some(description) = &listing.description {
        let short: String = description.chars().take(700).collect();
        text.push_str(&format!("\n\n📝 <b>Описание</b>\n{}", esc(&short)));
    }
    text.push_str(&format!("\n\n🔗 <a href=\"{}\">Открыть объявление</a>", esc(&listing.url)));

    let recipient = ChatId(chat_id);\n    if text.chars().count() > 1000 { text = text.chars().take(997).collect::<String>() + "..."; }
    if let Some(image) = listing.images.first() {
        if let Ok(url) = image.parse::<Url>() {
            bot.send_photo(recipient, InputFile::url(url)).caption(text).parse_mode(ParseMode::Html).await?;
            return Ok(());
        }
    }
    bot.send_message(recipient, text).parse_mode(ParseMode::Html).await?;
    Ok(())
}
