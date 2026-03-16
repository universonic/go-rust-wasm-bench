use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn json_roundtrip(input: &str) -> String {
    match shared::jsonrt::process(input.as_bytes()) {
        Ok(v) => String::from_utf8(v).unwrap_or_else(|_| "error: invalid utf8".into()),
        Err(e) => format!("error: {e}"),
    }
}
