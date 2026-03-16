# Go vs Rust WebAssembly Benchmark

A systematic benchmark comparing **Go** (standard compiler), **TinyGo**, and **Rust** for WebAssembly application development across browser and WASI environments.

## Benchmark Workloads

| Workload | Type | Environment |
|----------|------|-------------|
| Image Convolution (3×3 / 5×5) | Compute-intensive | Browser & WASI |
| JSON Serialize/Deserialize | Data processing | Browser & WASI |
| SHA-256 Hashing | Compute-intensive | WASI |

## Metrics

- **Compile-time**: Binary size (C1), build time (C2)
- **Runtime**: Module instantiation (R1), execution time (R2/R4/R5), memory usage (R3/R6)
- **Engineering**: Source lines of code (E1), toolchain complexity (E2)

Statistical significance is assessed using the Mann-Whitney U test.

## Project Structure

```
.
├── go/                  # Go source code (shared by Go & TinyGo compilers)
│   ├── conv/            #   Convolution algorithm
│   ├── jsonrt/          #   JSON round-trip logic
│   ├── sha/             #   SHA-256 hashing
│   └── cmd/             #   Browser & WASI entry points
├── rust/                # Rust source code (Cargo workspace)
│   ├── shared/          #   Shared algorithm library
│   ├── conv-browser/    #   Browser entry (wasm-bindgen)
│   ├── conv-wasi/       #   WASI entry
│   ├── json-browser/    #   Browser entry (wasm-bindgen)
│   ├── json-wasi/       #   WASI entry
│   └── sha-wasi/        #   WASI entry
├── harness/             # Benchmark harnesses
│   ├── browser/         #   Playwright-based browser benchmarks
│   ├── wasi/            #   Wasmtime-based WASI benchmarks (hyperfine)
│   └── build-time.sh    #   Build time measurement
├── results/             # Raw results & analysis scripts
│   ├── browser/         #   Browser benchmark results (JSON)
│   ├── wasi/            #   WASI benchmark results (JSON + TXT)
│   ├── figures/         #   Generated charts (PNG)
│   ├── generate_charts.py
│   └── print_tables.py
├── testdata/            # Input data & reference outputs for verification
├── Makefile             # Build & benchmark orchestration
└── DRAFT.md             # Thesis draft (Chinese)
```

## Prerequisites

- Go 1.24+
- TinyGo 0.37+
- Rust 1.86+ with `wasm32-unknown-unknown` and `wasm32-wasip1` targets
- [Wasmtime](https://wasmtime.dev/) (WASI runtime)
- [hyperfine](https://github.com/sharkdp/hyperfine) (CLI benchmark tool)
- Node.js 22+ with [Playwright](https://playwright.dev/) (browser benchmarks)
- Python 3.12+ with matplotlib, numpy, scipy (chart generation)

## Quick Start

```bash
# Build all Wasm modules (Go, TinyGo, Rust)
make all

# Verify correctness
make verify

# Run all benchmarks
make bench

# Generate charts (requires Python venv)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash results/generate_charts.sh

# Print data tables
bash results/print_tables.sh
```

## License

This project is licensed under the [MIT License](LICENSE).
