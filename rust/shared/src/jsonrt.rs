use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    pub id: i64,
    pub name: String,
    pub email: String,
    pub age: i64,
    pub score: f64,
}

pub fn process(input: &[u8]) -> Result<Vec<u8>, String> {
    let users: Vec<User> =
        serde_json::from_slice(input).map_err(|e| format!("deserialize: {e}"))?;

    let mut filtered: Vec<User> = users.into_iter().filter(|u| u.age >= 18).collect();

    filtered.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.id.cmp(&b.id))
    });

    serde_json::to_vec(&filtered).map_err(|e| format!("serialize: {e}"))
}
