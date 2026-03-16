use std::io::{self, Read, Write};
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();

    let mut iterations = 1usize;
    if args.len() >= 3 && args[1] == "--bench" {
        iterations = args[2].parse().unwrap();
    }

    let mut input = Vec::new();
    io::stdin().read_to_end(&mut input).unwrap();

    let (warmup, measured) = if iterations > 1 { (5, iterations - 5) } else { (0, 1) };

    let mut result = Vec::new();

    for _ in 0..warmup {
        result = shared::jsonrt::process(&input).unwrap();
    }

    for i in 0..measured {
        let start = Instant::now();
        result = shared::jsonrt::process(&input).unwrap();
        let elapsed = start.elapsed();
        if iterations > 1 {
            eprintln!("iteration {}: {:.6} ms", i + 1, elapsed.as_secs_f64() * 1000.0);
        }
    }

    io::stdout().write_all(&result).unwrap();
}
