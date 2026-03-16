use std::io::{self, Read, Write};
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 4 {
        eprintln!("usage: conv-wasi <width> <height> <kernel_size> [--bench N]");
        std::process::exit(1);
    }

    let w: usize = args[1].parse().unwrap();
    let h: usize = args[2].parse().unwrap();
    let kernel_size: usize = args[3].parse().unwrap();

    let mut iterations = 1usize;
    if args.len() >= 6 && args[4] == "--bench" {
        iterations = args[5].parse().unwrap();
    }

    let mut img = Vec::new();
    io::stdin().read_to_end(&mut img).unwrap();

    let expected = w * h * 4;
    if img.len() < expected {
        eprintln!("expected {} bytes, got {}", expected, img.len());
        std::process::exit(1);
    }
    img.truncate(expected);

    let kernel = shared::conv::kernel_by_size(kernel_size);

    let (warmup, measured) = if iterations > 1 { (5, iterations - 5) } else { (0, 1) };

    let mut result = Vec::new();

    for _ in 0..warmup {
        result = shared::conv::convolve(&img, w, h, kernel);
    }

    for i in 0..measured {
        let start = Instant::now();
        result = shared::conv::convolve(&img, w, h, kernel);
        let elapsed = start.elapsed();
        if iterations > 1 {
            eprintln!("iteration {}: {:.6} ms", i + 1, elapsed.as_secs_f64() * 1000.0);
        }
    }

    io::stdout().write_all(&result).unwrap();
}
