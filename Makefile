.PHONY: all clean go tinygo rust testdata \
       copy-wasm-exec bench-wasi bench-browser bench-build bench

BUILD     := build
TESTDATA  := testdata

export GOTOOLCHAIN := local
export CARGO_TARGET_DIR := $(CURDIR)/rust/target

# --- Go standard compiler ---
GO_BROWSER := $(BUILD)/conv-browser-go.wasm $(BUILD)/json-browser-go.wasm
GO_WASI    := $(BUILD)/conv-wasi-go.wasm $(BUILD)/json-wasi-go.wasm $(BUILD)/sha-wasi-go.wasm

$(BUILD)/conv-browser-go.wasm:
	GOOS=js GOARCH=wasm go build -ldflags="-s -w" -o $@ ./go/cmd/conv-browser

$(BUILD)/json-browser-go.wasm:
	GOOS=js GOARCH=wasm go build -ldflags="-s -w" -o $@ ./go/cmd/json-browser

$(BUILD)/conv-wasi-go.wasm:
	GOOS=wasip1 GOARCH=wasm go build -ldflags="-s -w" -o $@ ./go/cmd/conv-wasi

$(BUILD)/json-wasi-go.wasm:
	GOOS=wasip1 GOARCH=wasm go build -ldflags="-s -w" -o $@ ./go/cmd/json-wasi

$(BUILD)/sha-wasi-go.wasm:
	GOOS=wasip1 GOARCH=wasm go build -ldflags="-s -w" -o $@ ./go/cmd/sha-wasi

go: $(GO_BROWSER) $(GO_WASI)

# --- TinyGo ---
TINYGO_BROWSER := $(BUILD)/conv-browser-tinygo.wasm $(BUILD)/json-browser-tinygo.wasm
TINYGO_WASI    := $(BUILD)/conv-wasi-tinygo.wasm $(BUILD)/json-wasi-tinygo.wasm $(BUILD)/sha-wasi-tinygo.wasm

$(BUILD)/conv-browser-tinygo.wasm:
	tinygo build -target=wasm -opt=z -no-debug -o $@ ./go/cmd/conv-browser

$(BUILD)/json-browser-tinygo.wasm:
	tinygo build -target=wasm -opt=z -no-debug -o $@ ./go/cmd/json-browser

$(BUILD)/conv-wasi-tinygo.wasm:
	tinygo build -target=wasip1 -opt=z -no-debug -o $@ ./go/cmd/conv-wasi

$(BUILD)/json-wasi-tinygo.wasm:
	tinygo build -target=wasip1 -opt=z -no-debug -o $@ ./go/cmd/json-wasi

$(BUILD)/sha-wasi-tinygo.wasm:
	tinygo build -target=wasip1 -opt=z -no-debug -o $@ ./go/cmd/sha-wasi

tinygo: $(TINYGO_BROWSER) $(TINYGO_WASI)

# --- Rust ---
RUST_BROWSER := $(BUILD)/conv-browser-rust.wasm $(BUILD)/json-browser-rust.wasm
RUST_WASI    := $(BUILD)/conv-wasi-rust.wasm $(BUILD)/json-wasi-rust.wasm $(BUILD)/sha-wasi-rust.wasm

$(BUILD)/conv-browser-rust.wasm: rust-browser-build
	wasm-bindgen --target web --out-dir $(BUILD)/rust-conv-browser \
		rust/target/wasm32-unknown-unknown/release/conv_browser.wasm
	cp $(BUILD)/rust-conv-browser/conv_browser_bg.wasm $@

$(BUILD)/json-browser-rust.wasm: rust-browser-build
	wasm-bindgen --target web --out-dir $(BUILD)/rust-json-browser \
		rust/target/wasm32-unknown-unknown/release/json_browser.wasm
	cp $(BUILD)/rust-json-browser/json_browser_bg.wasm $@

.PHONY: rust-browser-build
rust-browser-build:
	cd rust && cargo build --release --target wasm32-unknown-unknown \
		-p conv-browser -p json-browser

$(BUILD)/conv-wasi-rust.wasm: rust-wasi-build
	cp rust/target/wasm32-wasip1/release/conv-wasi.wasm $@

$(BUILD)/json-wasi-rust.wasm: rust-wasi-build
	cp rust/target/wasm32-wasip1/release/json-wasi.wasm $@

$(BUILD)/sha-wasi-rust.wasm: rust-wasi-build
	cp rust/target/wasm32-wasip1/release/sha-wasi.wasm $@

.PHONY: rust-wasi-build
rust-wasi-build:
	cd rust && cargo build --release --target wasm32-wasip1 \
		-p conv-wasi -p json-wasi -p sha-wasi

rust: $(RUST_BROWSER) $(RUST_WASI)

# --- All ---
all: go tinygo rust

# --- Test data ---
testdata:
	go run testdata/generate.go

# --- Binary sizes ---
.PHONY: sizes
sizes:
	@echo "=== Binary sizes (bytes) ==="
	@for f in $(BUILD)/*.wasm; do \
		printf "%-40s %s\n" "$$(basename $$f)" "$$(wc -c < $$f | tr -d ' ')"; \
	done | sort

# --- Correctness verification ---
.PHONY: verify
verify:
	@echo "=== SHA-256 ==="
	@for tc in go tinygo rust; do \
		out=$$(wasmtime run $(BUILD)/sha-wasi-$${tc}.wasm < $(TESTDATA)/sha256_input_1KB.bin 2>/dev/null); \
		ref=$$(cat $(TESTDATA)/sha256_1KB_ref.txt); \
		if [ "$$ref" = "$$out" ]; then echo "  sha-wasi-$$tc: PASS"; \
		else echo "  sha-wasi-$$tc: FAIL"; fi; \
	done
	@echo "=== JSON (WASI, semantic) ==="
	@for tc in go tinygo rust; do \
		wasmtime run $(BUILD)/json-wasi-$${tc}.wasm < $(TESTDATA)/users_100.json > /tmp/json_verify_$${tc}.json 2>/dev/null; \
		if python3 -c "import json; a=json.load(open('$(TESTDATA)/users_100_ref.json')); b=json.load(open('/tmp/json_verify_$${tc}.json')); exit(0 if a==b else 1)"; \
		then echo "  json-wasi-$$tc: PASS"; else echo "  json-wasi-$$tc: FAIL"; fi; \
	done
	@echo "=== Convolution 256x256 K3 ==="
	@for tc in go tinygo rust; do \
		wasmtime run $(BUILD)/conv-wasi-$${tc}.wasm 256 256 3 < $(TESTDATA)/image_256x256.rgba > /tmp/conv_verify_$${tc}.rgba 2>/dev/null; \
		if cmp -s /tmp/conv_verify_$${tc}.rgba $(TESTDATA)/image_256x256_conv3_ref.rgba; \
		then echo "  conv-wasi-$$tc: PASS"; else echo "  conv-wasi-$$tc: FAIL"; fi; \
	done
	@echo "=== Convolution 256x256 K5 ==="
	@for tc in go tinygo rust; do \
		wasmtime run $(BUILD)/conv-wasi-$${tc}.wasm 256 256 5 < $(TESTDATA)/image_256x256.rgba > /tmp/conv5_verify_$${tc}.rgba 2>/dev/null; \
		if cmp -s /tmp/conv5_verify_$${tc}.rgba $(TESTDATA)/image_256x256_conv5_ref.rgba; \
		then echo "  conv-wasi-$$tc: PASS"; else echo "  conv-wasi-$$tc: FAIL"; fi; \
	done

# --- Copy wasm_exec.js for browser harness ---
GOROOT_DIR     := $(shell go env GOROOT)
TINYGOROOT_DIR := $(shell tinygo env TINYGOROOT)

copy-wasm-exec:
	cp "$(GOROOT_DIR)/lib/wasm/wasm_exec.js" harness/browser/wasm_exec_go.js
	cp "$(TINYGOROOT_DIR)/targets/wasm_exec.js" harness/browser/wasm_exec_tinygo.js

# --- Benchmark harnesses ---
bench-wasi: all
	bash harness/wasi/bench.sh

bench-browser: all copy-wasm-exec
	node harness/browser/bench.mjs

bench-build:
	bash harness/build-time.sh

bench: bench-build bench-wasi bench-browser

# --- Clean ---
clean:
	rm -rf $(BUILD)
	cd rust && CARGO_TARGET_DIR=target cargo clean
