package main

import (
	"syscall/js"

	"github.com/universonic/go-rust-wasm-bench/go/jsonrt"
)

func jsonRoundtrip(_ js.Value, args []js.Value) any {
	input := args[0].String()

	result, err := jsonrt.Process([]byte(input))
	if err != nil {
		return js.ValueOf("error: " + err.Error())
	}
	return js.ValueOf(string(result))
}

func main() {
	js.Global().Set("wasmJsonRoundtrip", js.FuncOf(jsonRoundtrip))
	select {}
}
