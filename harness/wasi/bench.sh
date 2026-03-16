#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="$ROOT/build"
TESTDATA="$ROOT/testdata"
RESULTS="$ROOT/results/wasi"

WARMUP=3
RUNS=30
BENCH_ITERS=35   # 5 warmup + 30 measured (internal loop)

mkdir -p "$RESULTS"

TOOLCHAINS=(go tinygo rust)

header() { printf '\n\e[1;34m>>> %s\e[0m\n' "$1"; }
sub()    { printf '\e[33m  [%s]\e[0m\n' "$1"; }

echo "============================================"
echo " WASI Benchmark Suite"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo " Wasmtime $(wasmtime --version)"
echo " hyperfine $(hyperfine --version)"
echo " Machine: $(uname -m) / $(sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -p)"
echo "============================================"

# ── Helpers ──────────────────────────────────────

collect_warm() {
    local label=$1 tc=$2 file=$3
    if [[ ! -f "$file" ]]; then echo "    $tc: MISSING"; return; fi
    python3 -c "
import sys, statistics
vals = []
for line in open('$file'):
    if 'iteration' in line:
        vals.append(float(line.strip().split()[-2]))
if not vals:
    print('    $tc: no data')
    sys.exit(0)
n = len(vals)
mean = statistics.mean(vals)
med  = statistics.median(vals)
sd   = statistics.stdev(vals) if n > 1 else 0
print(f'    $tc: n={n}  mean={mean:.4f} ms  median={med:.4f} ms  stdev={sd:.4f} ms  min={min(vals):.4f}  max={max(vals):.4f}')
"
}

collect_peak_rss() {
    local label=$1 wasm=$2
    shift 2
    local rss
    rss=$( (/usr/bin/time -l wasmtime run "$wasm" "$@" < "$INPUT_FILE" > /dev/null) 2>&1 \
        | grep 'maximum resident' | awk '{print $1}')
    echo "    ${label}: ${rss:-N/A} bytes"
    echo "${rss:-0}" > "$RESULTS/${TAG}_rss_${label}.txt"
}

# ── B3: SHA-256 ──────────────────────────────────

SHA_LABELS=(1KB 64KB 1MB 16MB)

for sl in "${SHA_LABELS[@]}"; do
    INPUT_FILE="$TESTDATA/sha256_input_${sl}.bin"
    TAG="sha256_${sl}"
    header "B3: SHA-256  size=$sl"

    sub "cold start (hyperfine)"
    hyperfine \
        --warmup "$WARMUP" --runs "$RUNS" \
        --export-json "$RESULTS/${TAG}_cold.json" \
        --command-name "go"     "wasmtime run $BUILD/sha-wasi-go.wasm     < $INPUT_FILE" \
        --command-name "tinygo" "wasmtime run $BUILD/sha-wasi-tinygo.wasm < $INPUT_FILE" \
        --command-name "rust"   "wasmtime run $BUILD/sha-wasi-rust.wasm   < $INPUT_FILE" \
        2>&1 | sed 's/^/    /'

    sub "warm execution (internal timing)"
    for tc in "${TOOLCHAINS[@]}"; do
        wasmtime run "$BUILD/sha-wasi-${tc}.wasm" --bench "$BENCH_ITERS" \
            < "$INPUT_FILE" > /dev/null 2> "$RESULTS/${TAG}_warm_${tc}.txt"
        collect_warm "$TAG" "$tc" "$RESULTS/${TAG}_warm_${tc}.txt"
    done

    sub "peak memory (/usr/bin/time)"
    for tc in "${TOOLCHAINS[@]}"; do
        collect_peak_rss "$tc" "$BUILD/sha-wasi-${tc}.wasm"
    done
done

# ── B4: JSON Round-trip ──────────────────────────

JSON_SIZES=(100 1000 10000)

for n in "${JSON_SIZES[@]}"; do
    INPUT_FILE="$TESTDATA/users_${n}.json"
    TAG="json_${n}"
    header "B4: JSON Round-trip  N=$n"

    sub "cold start (hyperfine)"
    hyperfine \
        --warmup "$WARMUP" --runs "$RUNS" \
        --export-json "$RESULTS/${TAG}_cold.json" \
        --command-name "go"     "wasmtime run $BUILD/json-wasi-go.wasm     < $INPUT_FILE" \
        --command-name "tinygo" "wasmtime run $BUILD/json-wasi-tinygo.wasm < $INPUT_FILE" \
        --command-name "rust"   "wasmtime run $BUILD/json-wasi-rust.wasm   < $INPUT_FILE" \
        2>&1 | sed 's/^/    /'

    sub "warm execution (internal timing)"
    for tc in "${TOOLCHAINS[@]}"; do
        wasmtime run "$BUILD/json-wasi-${tc}.wasm" --bench "$BENCH_ITERS" \
            < "$INPUT_FILE" > /dev/null 2> "$RESULTS/${TAG}_warm_${tc}.txt"
        collect_warm "$TAG" "$tc" "$RESULTS/${TAG}_warm_${tc}.txt"
    done

    sub "peak memory (/usr/bin/time)"
    for tc in "${TOOLCHAINS[@]}"; do
        collect_peak_rss "$tc" "$BUILD/json-wasi-${tc}.wasm"
    done
done

# ── B1-ref: Image Convolution (WASI cross-ref) ──

CONV_DIMS=("256:256" "512:512" "1024:1024" "1920:1080")
CONV_LABELS=("256x256" "512x512" "1024x1024" "1920x1080")
KERNELS=(3 5)

for ki in "${!KERNELS[@]}"; do
    ks="${KERNELS[$ki]}"
    for ci in "${!CONV_LABELS[@]}"; do
        label="${CONV_LABELS[$ci]}"
        IFS=: read -r w h <<< "${CONV_DIMS[$ci]}"
        INPUT_FILE="$TESTDATA/image_${label}.rgba"
        TAG="conv_${label}_k${ks}"
        header "B1-ref: Convolution  ${label}  K${ks}"

        sub "cold start (hyperfine)"
        hyperfine \
            --warmup "$WARMUP" --runs "$RUNS" \
            --export-json "$RESULTS/${TAG}_cold.json" \
            --command-name "go"     "wasmtime run $BUILD/conv-wasi-go.wasm     $w $h $ks < $INPUT_FILE" \
            --command-name "tinygo" "wasmtime run $BUILD/conv-wasi-tinygo.wasm $w $h $ks < $INPUT_FILE" \
            --command-name "rust"   "wasmtime run $BUILD/conv-wasi-rust.wasm   $w $h $ks < $INPUT_FILE" \
            2>&1 | sed 's/^/    /'

        sub "warm execution (internal timing)"
        for tc in "${TOOLCHAINS[@]}"; do
            wasmtime run "$BUILD/conv-wasi-${tc}.wasm" "$w" "$h" "$ks" --bench "$BENCH_ITERS" \
                < "$INPUT_FILE" > /dev/null 2> "$RESULTS/${TAG}_warm_${tc}.txt"
            collect_warm "$TAG" "$tc" "$RESULTS/${TAG}_warm_${tc}.txt"
        done

        sub "peak memory (/usr/bin/time)"
        for tc in "${TOOLCHAINS[@]}"; do
            collect_peak_rss "$tc" "$BUILD/conv-wasi-${tc}.wasm" "$w" "$h" "$ks"
        done
    done
done

echo ""
echo "============================================"
echo " WASI benchmarks complete."
echo " Results saved to: $RESULTS/"
echo "============================================"
