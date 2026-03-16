package main

import (
	"syscall/js"

	"github.com/universonic/go-rust-wasm-bench/go/conv"
)

func convolve(_ js.Value, args []js.Value) any {
	imgJS := args[0]
	w := args[1].Int()
	h := args[2].Int()
	kernelSize := args[3].Int()

	img := make([]byte, imgJS.Get("length").Int())
	js.CopyBytesToGo(img, imgJS)

	kernel := conv.KernelBySize(kernelSize)
	result := conv.Convolve(img, w, h, kernel)

	resultJS := js.Global().Get("Uint8Array").New(len(result))
	js.CopyBytesToJS(resultJS, result)
	return resultJS
}

func main() {
	js.Global().Set("wasmConvolve", js.FuncOf(convolve))
	select {}
}
