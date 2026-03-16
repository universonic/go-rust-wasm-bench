#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS="$ROOT/results"
REPS=5

export GOTOOLCHAIN=local
export CARGO_TARGET_DIR="$ROOT/rust/target"

mkdir -p "$RESULTS"

header() { printf '\n\e[1;34m>>> %s\e[0m\n' "$1"; }

echo "============================================"
echo " Build-time & Binary-size Measurement"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo " Repetitions: $REPS (median)"
echo "============================================"

ORDERED_KEYS=(
  go-conv-browser go-json-browser
  go-conv-wasi go-json-wasi go-sha-wasi
  tinygo-conv-browser tinygo-json-browser
  tinygo-conv-wasi tinygo-json-wasi tinygo-sha-wasi
  rust-browser rust-wasi
)

get_cmd() {
    case "$1" in
        go-conv-browser)    echo "GOOS=js GOARCH=wasm go build -ldflags='-s -w' -o build/conv-browser-go.wasm ./go/cmd/conv-browser" ;;
        go-json-browser)    echo "GOOS=js GOARCH=wasm go build -ldflags='-s -w' -o build/json-browser-go.wasm ./go/cmd/json-browser" ;;
        go-conv-wasi)       echo "GOOS=wasip1 GOARCH=wasm go build -ldflags='-s -w' -o build/conv-wasi-go.wasm ./go/cmd/conv-wasi" ;;
        go-json-wasi)       echo "GOOS=wasip1 GOARCH=wasm go build -ldflags='-s -w' -o build/json-wasi-go.wasm ./go/cmd/json-wasi" ;;
        go-sha-wasi)        echo "GOOS=wasip1 GOARCH=wasm go build -ldflags='-s -w' -o build/sha-wasi-go.wasm ./go/cmd/sha-wasi" ;;
        tinygo-conv-browser) echo "tinygo build -target=wasm -opt=z -no-debug -o build/conv-browser-tinygo.wasm ./go/cmd/conv-browser" ;;
        tinygo-json-browser) echo "tinygo build -target=wasm -opt=z -no-debug -o build/json-browser-tinygo.wasm ./go/cmd/json-browser" ;;
        tinygo-conv-wasi)   echo "tinygo build -target=wasip1 -opt=z -no-debug -o build/conv-wasi-tinygo.wasm ./go/cmd/conv-wasi" ;;
        tinygo-json-wasi)   echo "tinygo build -target=wasip1 -opt=z -no-debug -o build/json-wasi-tinygo.wasm ./go/cmd/json-wasi" ;;
        tinygo-sha-wasi)    echo "tinygo build -target=wasip1 -opt=z -no-debug -o build/sha-wasi-tinygo.wasm ./go/cmd/sha-wasi" ;;
        rust-browser)       echo "cd rust && cargo build --release --target wasm32-unknown-unknown -p conv-browser -p json-browser" ;;
        rust-wasi)          echo "cd rust && cargo build --release --target wasm32-wasip1 -p conv-wasi -p json-wasi -p sha-wasi" ;;
    esac
}

json_entries=()

for key in "${ORDERED_KEYS[@]}"; do
    cmd="$(get_cmd "$key")"
    header "$key"
    times=()

    for i in $(seq 1 "$REPS"); do
        case "$key" in
            go-*|tinygo-*)
                if [[ "$key" == tinygo-* ]]; then
                    tc=tinygo; target="${key#tinygo-}"
                else
                    tc=go; target="${key#go-}"
                fi
                rm -f "build/${target}-${tc}.wasm" 2>/dev/null || true
                go clean -cache 2>/dev/null || true
                ;;
            rust-browser)
                rm -rf rust/target/wasm32-unknown-unknown/release/deps 2>/dev/null || true
                rm -rf rust/target/wasm32-unknown-unknown/release/.fingerprint 2>/dev/null || true
                rm -f build/conv-browser-rust.wasm build/json-browser-rust.wasm 2>/dev/null || true
                ;;
            rust-wasi)
                rm -rf rust/target/wasm32-wasip1/release/deps 2>/dev/null || true
                rm -rf rust/target/wasm32-wasip1/release/.fingerprint 2>/dev/null || true
                rm -f build/conv-wasi-rust.wasm build/json-wasi-rust.wasm build/sha-wasi-rust.wasm 2>/dev/null || true
                ;;
        esac

        t0=$(python3 -c 'import time; print(time.monotonic())')
        (cd "$ROOT" && eval "$cmd") > /dev/null 2>&1
        t1=$(python3 -c 'import time; print(time.monotonic())')
        elapsed=$(python3 -c "print(f'{$t1 - $t0:.4f}')")
        times+=("$elapsed")
        printf "  run %d: %s s\n" "$i" "$elapsed"
    done

    times_csv=$(IFS=,; echo "${times[*]}")
    median=$(python3 -c "
import statistics
vals = [$times_csv]
print(f'{statistics.median(vals):.4f}')
")
    printf "  \e[32mmedian: %s s\e[0m\n" "$median"

    json_entries+=("\"$key\": { \"times\": [$times_csv], \"median\": $median }")
done

# Post-build: wasm-bindgen + copy for Rust so binary sizes are captured
mkdir -p "$ROOT/build/rust-conv-browser" "$ROOT/build/rust-json-browser"
wasm-bindgen --target web --out-dir "$ROOT/build/rust-conv-browser" \
    "$ROOT/rust/target/wasm32-unknown-unknown/release/conv_browser.wasm" 2>/dev/null || true
cp "$ROOT/build/rust-conv-browser/conv_browser_bg.wasm" "$ROOT/build/conv-browser-rust.wasm" 2>/dev/null || true
wasm-bindgen --target web --out-dir "$ROOT/build/rust-json-browser" \
    "$ROOT/rust/target/wasm32-unknown-unknown/release/json_browser.wasm" 2>/dev/null || true
cp "$ROOT/build/rust-json-browser/json_browser_bg.wasm" "$ROOT/build/json-browser-rust.wasm" 2>/dev/null || true
cp "$ROOT/rust/target/wasm32-wasip1/release/conv-wasi.wasm" "$ROOT/build/conv-wasi-rust.wasm" 2>/dev/null || true
cp "$ROOT/rust/target/wasm32-wasip1/release/json-wasi.wasm" "$ROOT/build/json-wasi-rust.wasm" 2>/dev/null || true
cp "$ROOT/rust/target/wasm32-wasip1/release/sha-wasi.wasm" "$ROOT/build/sha-wasi-rust.wasm" 2>/dev/null || true

# Binary sizes
header "Binary sizes"
size_entries=()
for f in "$ROOT"/build/*.wasm; do
    name=$(basename "$f")
    sz=$(wc -c < "$f" | tr -d ' ')
    printf "  %-42s %s bytes\n" "$name" "$sz"
    size_entries+=("\"$name\": $sz")
done

# Write JSON
{
    echo "{"
    echo "  \"build_times\": {"
    printf "    %s" "${json_entries[0]}"
    for ((i = 1; i < ${#json_entries[@]}; i++)); do
        printf ",\n    %s" "${json_entries[$i]}"
    done
    echo ""
    echo "  },"
    echo "  \"binary_sizes\": {"
    printf "    %s" "${size_entries[0]}"
    for ((i = 1; i < ${#size_entries[@]}; i++)); do
        printf ",\n    %s" "${size_entries[$i]}"
    done
    echo ""
    echo "  }"
    echo "}"
} > "$RESULTS/build-metrics.json"

echo ""
echo "============================================"
echo " Build-time measurement complete."
echo " Results saved to: $RESULTS/build-metrics.json"
echo "============================================"
