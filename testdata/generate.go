// Test data generator for all benchmarks.
// Run: go run testdata/generate.go
package main

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"math"
	"math/rand"
	"os"
	"path/filepath"
	"sort"
)

const seed = 42

type User struct {
	ID    int     `json:"id"`
	Name  string  `json:"name"`
	Email string  `json:"email"`
	Age   int     `json:"age"`
	Score float64 `json:"score"`
}

func randomName(rng *rand.Rand) string {
	length := 8 + rng.Intn(9) // 8-16
	b := make([]byte, length)
	for i := range b {
		b[i] = 'a' + byte(rng.Intn(26))
	}
	return string(b)
}

func generateUsers(n int) []User {
	rng := rand.New(rand.NewSource(seed))
	users := make([]User, n)
	for i := 0; i < n; i++ {
		name := randomName(rng)
		users[i] = User{
			ID:    i + 1,
			Name:  name,
			Email: name + "@example.com",
			Age:   10 + rng.Intn(71), // [10, 80]
			Score: math.Round(rng.Float64()*10000) / 100,
		}
	}
	return users
}

func processUsers(users []User) []User {
	var filtered []User
	for _, u := range users {
		if u.Age >= 18 {
			filtered = append(filtered, u)
		}
	}
	sort.Slice(filtered, func(i, j int) bool {
		if filtered[i].Score != filtered[j].Score {
			return filtered[i].Score > filtered[j].Score
		}
		return filtered[i].ID < filtered[j].ID
	})
	return filtered
}

func generateImage(width, height int) []byte {
	rng := rand.New(rand.NewSource(seed))
	buf := make([]byte, width*height*4)
	for i := 0; i < len(buf); i++ {
		buf[i] = byte(rng.Intn(256))
	}
	return buf
}

func convolve(img []byte, w, h int, kernel [][]float64) []byte {
	kSize := len(kernel)
	kHalf := kSize / 2
	out := make([]byte, w*h*4)

	var kSum float64
	for _, row := range kernel {
		for _, v := range row {
			kSum += v
		}
	}
	if kSum == 0 {
		kSum = 1
	}

	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			idx := (y*w + x) * 4
			for c := 0; c < 3; c++ {
				var sum float64
				for ky := 0; ky < kSize; ky++ {
					for kx := 0; kx < kSize; kx++ {
						iy := y + ky - kHalf
						ix := x + kx - kHalf
						if iy >= 0 && iy < h && ix >= 0 && ix < w {
							sum += float64(img[(iy*w+ix)*4+c]) * kernel[ky][kx]
						}
					}
				}
				val := sum / kSum
				if val < 0 {
					val = 0
				} else if val > 255 {
					val = 255
				}
				out[idx+c] = byte(math.Round(val))
			}
			out[idx+3] = img[idx+3] // copy alpha
		}
	}
	return out
}

func generateSHAInput(size int) []byte {
	buf := make([]byte, size)
	for i := range buf {
		buf[i] = byte(i % 256)
	}
	return buf
}

func main() {
	dir := "testdata"
	os.MkdirAll(dir, 0o755)

	// --- JSON test data & reference ---
	jsonSizes := []int{100, 1000, 10000}
	for _, n := range jsonSizes {
		users := generateUsers(n)
		data, _ := json.Marshal(users)
		os.WriteFile(filepath.Join(dir, fmt.Sprintf("users_%d.json", n)), data, 0o644)

		result := processUsers(users)
		ref, _ := json.Marshal(result)
		os.WriteFile(filepath.Join(dir, fmt.Sprintf("users_%d_ref.json", n)), ref, 0o644)

		fmt.Printf("JSON N=%d: %d users → %d filtered, input %d bytes, ref %d bytes\n",
			n, len(users), len(result), len(data), len(ref))
	}

	// --- Image test data & convolution reference ---
	kernel3 := [][]float64{
		{1, 2, 1},
		{2, 4, 2},
		{1, 2, 1},
	}
	kernel5 := [][]float64{
		{1, 4, 6, 4, 1},
		{4, 16, 24, 16, 4},
		{6, 24, 36, 24, 6},
		{4, 16, 24, 16, 4},
		{1, 4, 6, 4, 1},
	}

	imageSizes := [][2]int{{256, 256}, {512, 512}, {1024, 1024}, {1920, 1080}}
	for _, sz := range imageSizes {
		w, h := sz[0], sz[1]
		img := generateImage(w, h)
		os.WriteFile(filepath.Join(dir, fmt.Sprintf("image_%dx%d.rgba", w, h)), img, 0o644)

		ref3 := convolve(img, w, h, kernel3)
		os.WriteFile(filepath.Join(dir, fmt.Sprintf("image_%dx%d_conv3_ref.rgba", w, h)), ref3, 0o644)

		ref5 := convolve(img, w, h, kernel5)
		os.WriteFile(filepath.Join(dir, fmt.Sprintf("image_%dx%d_conv5_ref.rgba", w, h)), ref5, 0o644)

		fmt.Printf("Image %dx%d: %d bytes, conv3 ref %d bytes, conv5 ref %d bytes\n",
			w, h, len(img), len(ref3), len(ref5))
	}

	// --- SHA-256 test data & reference ---
	shaSizes := []int{1024, 65536, 1048576, 16777216}
	shaLabels := []string{"1KB", "64KB", "1MB", "16MB"}
	for i, size := range shaSizes {
		data := generateSHAInput(size)
		os.WriteFile(filepath.Join(dir, fmt.Sprintf("sha256_input_%s.bin", shaLabels[i])), data, 0o644)

		hash := sha256.Sum256(data)
		hashHex := fmt.Sprintf("%x", hash)
		os.WriteFile(filepath.Join(dir, fmt.Sprintf("sha256_%s_ref.txt", shaLabels[i])), []byte(hashHex), 0o644)

		fmt.Printf("SHA-256 %s: input %d bytes, hash %s\n", shaLabels[i], len(data), hashHex)
	}

	fmt.Println("\nAll test data generated successfully.")
}
