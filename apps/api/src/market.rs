use chrono::{DateTime, Utc};
use serde_json::{json, Value};
use sqlx::PgPool;
use std::collections::HashSet;

#[derive(sqlx::FromRow)]
struct Candidate{title:String,price:f64,first_seen_at:DateTime<Utc>,attributes:Value}

fn tokens(text:&str)->HashSet<String>{text.to_lowercase().split(|c:char|!c.is_alphanumeric()).filter(|s|s.len()>=2).filter(|s|!matches!(*s,"для"|"и"|"в"|"на"|"с"|"из"|"по"|"the"|"for"|"with"|"gb"|"гб")).map(ToOwned::to_owned).collect()}
fn identity_tokens(title:&str)->HashSet<String>{tokens(title).into_iter().filter(|t|t.chars().any(|c|c.is_ascii_digit())||t.len()>=4).collect()}

pub fn extract_attributes(title:&str, description:Option<&str>)->Value{
 let text=format!("{} {}",title,description.unwrap_or_default()).to_lowercase();
 let mut a=json!({});
 let pats=[("storage_gb",r"(\d{2,4})\s*(?:gb|гб)"),("ram_gb",r"(?:ram|озу)\s*(\d{1,2})\s*(?:gb|гб)?"),("year",r"\b(20(?:1[5-9]|2[0-9]))\b")];
 for (k,p) in pats { if let Ok(re)=regex::Regex::new(p) { if let Some(c)=re.captures(&text){if let Some(v)=c.get(1){a[k]=json!(v.as_str().parse::<i64>().unwrap_or(0));}}}}
 let condition=if text.contains("нов")||text.contains("new") {"new"} else if text.contains("б/у")||text.contains("бу")||text.contains("used") {"used"} else {""};
 if !condition.is_empty(){a["condition"]=json!(condition);}
 let brands=["apple","iphone","samsung","xiaomi","huawei","sony","google","lenovo","asus","acer","dell","hp","playstation","xbox"];
 for b in brands {if text.contains(b){a["brand"]=json!(b);break;}}
 a
}

fn attr_score(w:&Value,h:&Value)->f64{
 let mut score=1.0;
 for k in ["brand","condition","storage_gb","ram_gb","year"] {
  if let Some(x)=w.get(k){if let Some(y)=h.get(k){if x!=y{return 0.0}else{score+=0.45}}}
 }
 score
}
fn weighted_median(values:&mut[(f64,f64)])->Option<f64>{if values.is_empty(){return None}values.sort_by(|a,b|a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));let total:f64=values.iter().map(|(_,w)|*w).sum();if total<=0.0{return None}let mut acc=0.0;for(v,w)in values.iter(){acc+=*w;if acc>=total/2.0{return Some(*v)}}values.last().map(|x|x.0)}

pub async fn estimate(pool:&PgPool,title:&str,description:Option<&str>,exclude_id:Option<uuid::Uuid>)->(Option<f64>,Option<f64>){
 let wanted=tokens(title);if wanted.is_empty(){return(None,None)}let identity=identity_tokens(title);let attrs=extract_attributes(title,description);
 let mut key_parts:Vec<_>=wanted.iter().cloned().collect();key_parts.sort();let cache_key=format!("market:v3:{}:{}",key_parts.join("|"),serde_json::to_string(&attrs).unwrap_or_default());
 if let Ok(url)=std::env::var("REDIS_URL"){if let Ok(client)=redis::Client::open(url){if let Ok(mut conn)=client.get_multiplexed_async_connection().await{if let Ok(Some(raw))=redis::AsyncCommands::get::<_,Option<String>>(&mut conn,&cache_key).await{let mut p=raw.split(':');if let(Some(a),Some(b))=(p.next(),p.next()){if let(Ok(price),Ok(conf))=(a.parse::<f64>(),b.parse::<f64>()){return(Some(price),Some(conf));}}}}}}
 let rows=sqlx::query_as::<_,Candidate>("SELECT title,price,first_seen_at,attributes FROM listings WHERE price IS NOT NULL AND price>0 AND status='active' AND ($1::uuid IS NULL OR id<>$1) ORDER BY first_seen_at DESC LIMIT 1000").bind(exclude_id).fetch_all(pool).await.unwrap_or_default();
 let now=Utc::now();let mut scored=Vec::new();
 for row in rows{
  let have=tokens(&row.title);let overlap=wanted.intersection(&have).count()as f64;let sim=overlap/wanted.len().max(1)as f64;if overlap==0.0||sim<0.30{continue}
  let have_id=identity_tokens(&row.title);let id_overlap=identity.intersection(&have_id).count()as f64;let identity_sim=if identity.is_empty(){sim}else{id_overlap/identity.len().max(1)as f64};if !identity.is_empty()&&identity_sim<0.34{continue}
  let a_score=attr_score(&attrs,&row.attributes);if a_score==0.0{continue}
  let age_days=(now-row.first_seen_at).num_seconds().max(0)as f64/86400.0;let recency=1.0/(1.0+age_days/14.0);
  let exact_bonus=if identity_sim>=0.75{1.35}else if identity_sim>=0.5{1.0}else{0.7};
  let weight=(0.2+sim*1.6)*identity_sim.max(0.35)*exact_bonus*recency*a_score;scored.push((row.price,weight));
 }
 if scored.len()<5{return(None,None)}
 scored.sort_by(|a,b|a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));let q1=scored[scored.len()/4].0;let q3=scored[(scored.len()*3)/4].0;let iqr=(q3-q1).max(0.0);let low=if iqr>0.0{q1-1.5*iqr}else{q1*0.7};let high=if iqr>0.0{q3+1.5*iqr}else{q3*1.3};let mut filtered:Vec<_>=scored.into_iter().filter(|(p,_)|*p>=low&&*p<=high).collect();if filtered.len()<5{return(None,None)}
 let market=weighted_median(&mut filtered);let sample_factor=(filtered.len()as f64/25.0).min(1.0);let total:f64=filtered.iter().map(|(_,w)|*w).sum();let confidence=(sample_factor*(total/20.0).min(1.0)).clamp(0.0,1.0);let result=(market,Some(confidence));
 if let(Some(price),Some(conf))=result{if let Ok(url)=std::env::var("REDIS_URL"){if let Ok(client)=redis::Client::open(url){if let Ok(mut conn)=client.get_multiplexed_async_connection().await{let _:Result<(),_>=redis::AsyncCommands::set_ex(&mut conn,&cache_key,format!("{price}:{conf}"),15).await;}}}}
 result
}