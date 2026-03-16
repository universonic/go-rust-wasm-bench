use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn convolve(img: &[u8], w: u32, h: u32, kernel_size: u32) -> Vec<u8> {
    let kernel = shared::conv::kernel_by_size(kernel_size as usize);
    shared::conv::convolve(img, w as usize, h as usize, kernel)
}
