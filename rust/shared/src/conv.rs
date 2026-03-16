pub const KERNEL3: &[&[f64]] = &[
    &[1.0, 2.0, 1.0],
    &[2.0, 4.0, 2.0],
    &[1.0, 2.0, 1.0],
];

pub const KERNEL5: &[&[f64]] = &[
    &[1.0, 4.0, 6.0, 4.0, 1.0],
    &[4.0, 16.0, 24.0, 16.0, 4.0],
    &[6.0, 24.0, 36.0, 24.0, 6.0],
    &[4.0, 16.0, 24.0, 16.0, 4.0],
    &[1.0, 4.0, 6.0, 4.0, 1.0],
];

pub fn kernel_by_size(size: usize) -> &'static [&'static [f64]] {
    if size == 5 { KERNEL5 } else { KERNEL3 }
}

pub fn convolve(img: &[u8], w: usize, h: usize, kernel: &[&[f64]]) -> Vec<u8> {
    let k_size = kernel.len();
    let k_half = k_size / 2;
    let mut out = vec![0u8; w * h * 4];

    let k_sum: f64 = kernel.iter().flat_map(|row| row.iter()).sum();
    let k_sum = if k_sum == 0.0 { 1.0 } else { k_sum };

    for y in 0..h {
        for x in 0..w {
            let idx = (y * w + x) * 4;
            for c in 0..3usize {
                let mut sum = 0.0f64;
                for ky in 0..k_size {
                    for kx in 0..k_size {
                        let iy = y as isize + ky as isize - k_half as isize;
                        let ix = x as isize + kx as isize - k_half as isize;
                        if iy >= 0 && iy < h as isize && ix >= 0 && ix < w as isize {
                            let src_idx = (iy as usize * w + ix as usize) * 4 + c;
                            sum += img[src_idx] as f64 * kernel[ky][kx];
                        }
                    }
                }
                let val = (sum / k_sum).round().clamp(0.0, 255.0);
                out[idx + c] = val as u8;
            }
            out[idx + 3] = img[idx + 3];
        }
    }
    out
}
