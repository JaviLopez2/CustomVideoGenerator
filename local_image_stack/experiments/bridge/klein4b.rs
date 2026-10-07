use serde_json::{Map, Value, json};
use std::collections::HashSet;

pub const ALIASES: [&str; 2] = ["flux-klein-4b-t2i-exp", "flux-klein-4b-edit-exp"];

pub fn is_alias(alias: &str) -> bool {
    ALIASES.contains(&alias)
}

pub fn materialize(request: &Map<String, Value>, template: &Value) -> Result<Value, String> {
    let invalid = || "Invalid Klein 4B experimental request".to_string();
    let alias = request
        .get("model")
        .and_then(Value::as_str)
        .ok_or_else(invalid)?;
    if !is_alias(alias) {
        return Err(invalid());
    }
    let prompt = request
        .get("prompt")
        .and_then(Value::as_str)
        .ok_or_else(invalid)?;
    let seed = request
        .get("seed")
        .and_then(Value::as_i64)
        .ok_or_else(invalid)?;
    if prompt.trim().is_empty() || seed < 0 {
        return Err(invalid());
    }
    for (key, expected) in [("steps", 4), ("n", 1)] {
        if request.get(key).and_then(Value::as_i64) != Some(expected) {
            return Err(invalid());
        }
    }
    if request.get("guidance").and_then(Value::as_f64) != Some(1.0) {
        return Err(invalid());
    }
    let dimensions: Vec<u32> = request
        .get("size")
        .and_then(Value::as_str)
        .ok_or_else(invalid)?
        .split('x')
        .map(str::parse)
        .collect::<Result<_, _>>()
        .map_err(|_| invalid())?;
    if dimensions.len() != 2
        || dimensions
            .iter()
            .any(|n| *n == 0 || *n > 16384 || n % 16 != 0)
    {
        return Err(invalid());
    }
    let fields = ["reference_image", "reference_image_2", "reference_image_3"];
    if request.keys().any(|k| {
        (k.starts_with("reference_image") && !fields.contains(&k.as_str()))
            || k == "style_reference_image"
    }) {
        return Err("Only three ordered experimental reference slots are supported".into());
    }
    let mut refs = Vec::new();
    let mut seen = HashSet::new();
    let mut missing = false;
    for field in fields {
        match request.get(field) {
            None => missing = true,
            Some(value) => {
                let name = value.as_str().ok_or_else(invalid)?.replace('\\', "/");
                if missing
                    || name.trim().is_empty()
                    || name.starts_with('/')
                    || name.contains(':')
                    || name.split('/').any(|p| p == "..")
                    || !seen.insert(name.clone())
                {
                    return Err(
                        "References must be contiguous, unique relative Comfy input filenames"
                            .into(),
                    );
                }
                refs.push(name);
            }
        }
    }
    if (alias == ALIASES[0] && !refs.is_empty()) || (alias == ALIASES[1] && refs.is_empty()) {
        return Err("T2I requires zero references; Edit requires one to three".into());
    }
    if refs.is_empty()
        && request
            .get("reference_roles")
            .is_some_and(|roles| roles.as_array().is_none_or(|v| !v.is_empty()))
    {
        return Err("T2I must not contain reference roles".into());
    }
    let mut model_prompt = prompt.trim().to_string();
    let mut has_root = false;
    if !refs.is_empty() {
        let roles = request
            .get("reference_roles")
            .and_then(Value::as_array)
            .ok_or_else(invalid)?;
        let allowed = [
            "identity_reference",
            "factual_reference",
            "style_reference",
            "continuity_anchor",
        ];
        if roles.len() != refs.len()
            || roles
                .iter()
                .any(|v| !allowed.contains(&v.as_str().unwrap_or("")))
            || roles
                .iter()
                .filter(|v| v.as_str() == Some("continuity_anchor"))
                .count()
                > 1
        {
            return Err("Ordered reference roles are required".into());
        }
        for (index, role) in roles.iter().enumerate() {
            let role = role.as_str().unwrap();
            let clause = format!("Input image {} has role {}.", index + 1, role);
            if !model_prompt.contains(&clause) {
                model_prompt.push_str(&format!("\n{clause}"));
            }
            if role == "continuity_anchor" {
                has_root = true;
                let clause = format!(
                    "Use image {} as the stable root of the same physical subject. Preserve its identity and appropriate geometry/composition; physical identity does not require preserving the previous visual state.",
                    index + 1
                );
                if !model_prompt.contains(&clause) {
                    model_prompt.push_str(&format!("\n{clause}"));
                }
            }
        }
    }
    let temporal = match request.get("temporal_progression") {
        None => false,
        Some(v) => v.as_bool().ok_or_else(invalid)?,
    };
    let state = match request.get("temporal_state") {
        None => "",
        Some(v) => v.as_str().ok_or_else(invalid)?.trim(),
    };
    if temporal {
        let lower = prompt.to_lowercase();
        if !has_root
            || state.is_empty()
            || [
                "keep all visible content unchanged",
                "underlying depicted content unchanged",
                "preserve the previous visual state",
                "preserve previous state",
                "preserve the prior visual state",
                "preserve prior state",
            ]
            .iter()
            .any(|phrase| lower.contains(phrase))
        {
            return Err("Invalid temporal continuity contract".into());
        }
        let clause = format!("The result MUST advance to this requested visible state: {state}.");
        if !model_prompt.contains(&clause) {
            model_prompt.push_str(&format!("\n{clause}"));
        }
    } else if !state.is_empty() {
        return Err("Temporal state requires temporal_progression".into());
    }
    let mut graph = template.clone();
    for (node, field, name) in [
        ("1", "unet_name", "flux-2-klein-4b-fp8.safetensors"),
        ("2", "clip_name", "qwen_3_4b.safetensors"),
        ("3", "vae_name", "flux2-vae.safetensors"),
    ] {
        if graph[node]["inputs"][field].as_str() != Some(name) {
            return Err("Experimental template must target the declared 4B assets".into());
        }
    }
    graph["4"]["inputs"]["text"] = json!(model_prompt);
    graph["7"]["inputs"]["noise_seed"] = json!(seed);
    graph["9"]["inputs"] = json!({"steps":4,"width":dimensions[0],"height":dimensions[1]});
    graph["10"]["inputs"] = json!({"width":dimensions[0],"height":dimensions[1],"batch_size":1});
    graph["6"]["inputs"]["cfg"] = json!(1.0);
    if !refs.is_empty() {
        let nodes = graph.as_object_mut().ok_or_else(invalid)?;
        let mut block = Vec::new();
        for id in 20..25 {
            block.push(nodes.remove(&id.to_string()).ok_or_else(invalid)?);
        }
        let mut positive = json!(["4", 0]);
        let mut negative = json!(["5", 0]);
        for (index, filename) in refs.iter().enumerate() {
            let offset = index * 5;
            for (i, original) in block.iter().enumerate() {
                let mut node = original.clone();
                for value in node["inputs"]
                    .as_object_mut()
                    .ok_or_else(invalid)?
                    .values_mut()
                {
                    if let Some(link) = value.as_array() {
                        if let Some(source) = link
                            .first()
                            .and_then(Value::as_str)
                            .and_then(|s| s.parse::<usize>().ok())
                        {
                            if (20..25).contains(&source) {
                                *value = json!([(source + offset).to_string(), link[1]]);
                            }
                        }
                    }
                }
                nodes.insert((20 + i + offset).to_string(), node);
            }
            let image = (20 + offset).to_string();
            let pos = (23 + offset).to_string();
            let neg = (24 + offset).to_string();
            nodes.get_mut(&image).unwrap()["inputs"]["image"] = json!(filename);
            nodes.get_mut(&image).unwrap()["_meta"]["title"] =
                json!(format!("Subject Reference {}", index + 1));
            nodes.get_mut(&pos).unwrap()["inputs"]["conditioning"] = positive;
            nodes.get_mut(&neg).unwrap()["inputs"]["conditioning"] = negative;
            positive = json!([pos, 0]);
            negative = json!([neg, 0]);
        }
        nodes.get_mut("6").ok_or_else(invalid)?["inputs"]["positive"] = positive;
        nodes.get_mut("6").ok_or_else(invalid)?["inputs"]["negative"] = negative;
    }
    Ok(graph)
}
