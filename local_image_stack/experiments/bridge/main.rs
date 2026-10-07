//! Isolated bridge. Default is CLI-only; preview never submits a Comfy prompt.
#[path = "../../bridge/comfyui.rs"]
mod comfyui;
mod klein4b;
#[path = "../../bridge/proxy.rs"]
mod proxy;
#[path = "../../bridge/ws.rs"]
mod ws;

use axum::{
    Json, Router,
    body::Bytes,
    extract::State,
    http::StatusCode,
    routing::{any, get, post},
};
use serde_json::{Value, json};
use std::{collections::HashMap, sync::Arc, time::Duration};

fn workflows() -> Result<Arc<HashMap<String, Value>>, String> {
    let folder = concat!(env!("CARGO_MANIFEST_DIR"), "/../workflows");
    let loaded = comfyui::WorkflowsLoader::load_from_folder(folder)?;
    let pinned = [
        include_str!("../workflows/flux-klein-4b-t2i-exp.json"),
        include_str!("../workflows/flux-klein-4b-edit-exp.json"),
    ];
    if loaded.len() != 2 {
        return Err("Experimental folder must contain exactly two aliases".into());
    }
    for (alias, text) in klein4b::ALIASES.iter().zip(pinned) {
        let expected: Value = serde_json::from_str(text).map_err(|e| e.to_string())?;
        if loaded.get(*alias) != Some(&expected) {
            return Err("Template differs from compiled experimental binding".into());
        }
    }
    Ok(Arc::new(loaded))
}

async fn preview(
    State(state): State<Arc<proxy::ProxyState>>,
    body: Bytes,
) -> Result<Json<Value>, proxy::ProxyError> {
    let bytes = transform(body, state.workflows.clone()).await?;
    let value: Value = serde_json::from_slice(&bytes)?;
    Ok(Json(
        json!({"comfy_request":value,"dispatch_allowed":false}),
    ))
}

async fn transform(
    body: Bytes,
    workflows: Arc<HashMap<String, Value>>,
) -> Result<Bytes, proxy::ProxyError> {
    let request: Value = serde_json::from_slice(&body)?;
    if !request
        .get("model")
        .and_then(Value::as_str)
        .is_some_and(klein4b::is_alias)
    {
        return Err(proxy::ProxyError::Validation(
            "Expected an experimental Klein 4B alias".into(),
        ));
    }
    comfyui::create_json_payload(body, workflows, "klein4b-preview".into(), "preview").await
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let workflows = workflows()?;
    if args.len() == 2 && args[0] == "--dry-run" {
        let body = Bytes::from(std::fs::read(&args[1])?);
        let bytes = transform(body, workflows)
            .await
            .map_err(|e| format!("{e:?}"))?;
        println!(
            "{}",
            json!({"comfy_request":serde_json::from_slice::<Value>(&bytes)?,"dispatch_allowed":false})
        );
        return Ok(());
    }
    if args.len() != 1 || !["--serve-preview", "--serve-gpu"].contains(&args[0].as_str()) {
        return Err(
            "Usage: --dry-run FILE | --serve-preview | --serve-gpu (requires GPU authorization)"
                .into(),
        );
    }
    let gpu = args[0] == "--serve-gpu";
    let state = Arc::new(proxy::ProxyState {
        client: reqwest::Client::builder()
            .no_proxy()
            .timeout(Duration::from_secs(300))
            .build()?,
        backend_url: "127.0.0.1".into(),
        backend_port: "8188".into(),
        backend_client_id: "mpt-klein4b-experimental".into(),
        max_payload_size_mb: 64,
        timeout: 310,
        use_ws: false,
        ws_manager: None,
        workflows,
    });
    let mut app = Router::new()
        .route("/health", get(move || async move { Json(json!({"status":"ok","gpu_enabled":gpu})) }))
        .route("/v1/models", get(|| async { Json(json!({"object":"list","data":klein4b::ALIASES.map(|id| json!({"id":id,"object":"model"}))})) }))
        .route("/experimental/preview", post(preview));
    app = if gpu {
        app.route("/v1/images/*path", any(proxy::proxy_handler))
    } else {
        app.route(
            "/v1/images/*path",
            any(|| async {
                (
                    StatusCode::FORBIDDEN,
                    Json(json!({"error":"GPU dispatch disabled in preview mode"})),
                )
            }),
        )
    };
    let app = app
        .layer(tower_http::limit::RequestBodyLimitLayer::new(
            64 * 1024 * 1024,
        ))
        .with_state(state);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:8091").await?;
    axum::serve(listener, app)
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn legacy_payload_keeps_its_existing_parameter_path() {
        let graph = json!({"1":{"class_type":"CLIPTextEncode","_meta":{"title":"Positive Prompt"},"inputs":{"text":"old","clip":["2",0]}},
            "2":{"class_type":"CLIPLoader","inputs":{"clip_name":"existing-encoder"}},
            "3":{"class_type":"RandomNoise","inputs":{"noise_seed":0}}});
        let map = Arc::new(HashMap::from([("qwen-image-2.1-precision".into(), graph)]));
        let body = Bytes::from(
            serde_json::to_vec(
                &json!({"model":"qwen-image-2.1-precision","prompt":"existing prompt","seed":23}),
            )
            .unwrap(),
        );
        let result = comfyui::create_json_payload(body, map, "legacy".into(), "test")
            .await
            .unwrap();
        let output: Value = serde_json::from_slice(&result).unwrap();
        assert_eq!(output["prompt"]["1"]["inputs"]["text"], "existing prompt");
        assert_eq!(output["prompt"]["3"]["inputs"]["noise_seed"], 23);
        assert_eq!(
            output["prompt"]["2"]["inputs"]["clip_name"],
            "existing-encoder"
        );
    }
}
