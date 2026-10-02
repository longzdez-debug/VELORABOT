use sha2::{Digest,Sha256};
use std::env;

fn fingerprint(url:&str, title:&str, price:&str)->String {
    let mut h=Sha256::new();
    h.update(url.as_bytes());
    h.update(title.trim().to_lowercase().as_bytes());
    h.update(price.as_bytes());
    format!("{:x}", h.finalize())
}

#[tokio::main]
async fn main() {
    let url=env::var("VELORA_COLLECTOR_URL").unwrap_or_default();
    if url.is_empty() {
        println!("VELORA collector idle: VELORA_COLLECTOR_URL is not configured");
        return;
    }
    let client=reqwest::Client::builder().user_agent("VELORA/0.1").build().unwrap();
    match client.get(&url).send().await {
        Ok(r) => match r.text().await {
            Ok(body) => println!("collector fetched {} bytes; source fingerprint {}", body.len(), fingerprint(&url,"source",&body.len().to_string())),
            Err(e) => eprintln!("body error: {e}"),
        },
        Err(e) => eprintln!("request error: {e}"),
    }
}
