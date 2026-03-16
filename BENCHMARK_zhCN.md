# 基准测试方案：Go 与 Rust 在 WebAssembly 应用开发中的对比

## 1. 概述

本文档描述了用于对比 **Go**（标准编译器和 TinyGo）与 **Rust** 在 WebAssembly（Wasm）应用开发中表现的基准测试方案。测试涵盖**浏览器端**和**基于 WASI 的微服务**两个部署场景，每个场景各设两个测试用例，共计**四个测试用例**。每个测试用例均基于真实世界 Wasm 工作负载的实证研究，力求简洁、严谨且可复现。

### 1.1 工具链矩阵

每个测试用例由三条工具链分别编译，各生成一个 `.wasm` 产物：

| 工具链 | 浏览器目标 | WASI 目标 |
|--------|-----------|-----------|
| **Go（标准）** | `GOOS=js GOARCH=wasm` | `GOOS=wasip1 GOARCH=wasm` |
| **TinyGo** | `tinygo build -target=wasm` | `tinygo build -target=wasip1` |
| **Rust** | `wasm32-unknown-unknown` + wasm-bindgen | `wasm32-wasip1` |

### 1.2 测试用例汇总

| 编号 | 测试用例 | 场景 | 负载类型 |
|------|---------|------|---------|
| B1 | 图像卷积 | 浏览器 | 计算密集 + 内存访问密集 |
| B2 | JSON 往返处理 | 浏览器 | 数据处理 + JS-Wasm 交互 |
| B3 | SHA-256 哈希 | 微服务（WASI） | 纯计算密集（整数运算） |
| B4 | JSON 往返处理 | 微服务（WASI） | 数据序列化 / 反序列化 |

---

## 2. 测试用例

### 2.1 B1 — 图像卷积（浏览器）

#### 2.1.1 覆盖场景

图像卷积代表了浏览器端 Wasm 中**计算密集型像素级处理**的工作模式，该模式构成了相当比例的浏览器端 Wasm 负载：

- **媒体处理 / 播放器**（占 Web 端 Wasm 二进制的 9%）——直接匹配：像素级滤波与变换是媒体处理应用的核心操作。
- **可视化 / 动画**（11%）——渲染滤镜和视觉特效使用相同的滑窗式密集算术模式。
- **游戏**（25%）——部分覆盖：游戏引擎使用类似的密集数值计算（物理引擎、粒子效果、后处理）。

生产实例包括 Figma（C++ 渲染引擎编译为 Wasm，加载时间降低 3 倍 [R1]）、Adobe Photoshop Web（图像处理在 Wasm 中运行）及 PSPDFKit（通过 Wasm 实现 PDF 渲染）。

**预估覆盖率**：约 25%–35% 的浏览器端 Wasm 用例与图像卷积共享相同的核心计算模式。

#### 2.1.2 设计理由

选择图像卷积而非更简单的替代方案（如灰度转换）的原因：

1. 同时考验**计算密集度**（每像素多次乘加运算）和**内存访问局部性**（滑窗模式），这是 Wasm 执行性能的两个主导因素 [R2]。
2. 一项同行评审研究（SPIE 2023）直接验证了图像卷积作为 Wasm 代表性基准的有效性，发现 Wasm 在该负载上相比 JavaScript 有显著加速 [R3]。
3. 通过同时测试两种卷积核尺寸（3×3 和 5×5），可以观察性能随算术密集度的变化趋势——这是理解编译器优化效果的关键因素。

#### 2.1.3 规格定义

**输入**：
- RGBA 像素缓冲区（每像素 4 字节），像素值由**固定种子 42** 的 PRNG 生成。
- 图像尺寸（宽 × 高）：`256×256`、`512×512`、`1024×1024`、`1920×1080`。

**操作**：
- 使用以下归一化高斯卷积核进行二维卷积：

  3×3 高斯卷积核（σ ≈ 0.85）：

  ```
  K3 = (1/16) * [[1, 2, 1],
                  [2, 4, 2],
                  [1, 2, 1]]
  ```

  5×5 高斯卷积核（σ ≈ 1.0）：

  ```
  K5 = (1/256) * [[1,  4,  6,  4, 1],
                   [4, 16, 24, 16, 4],
                   [6, 24, 36, 24, 6],
                   [4, 16, 24, 16, 4],
                   [1,  4,  6,  4, 1]]
  ```

- 卷积**逐通道**进行（R、G、B 独立处理；A 通道直接复制）。
- 边界处理：**零填充**（越界像素视为 0）。
- 输出像素值钳位至 `[0, 255]` 并四舍五入取整。

**输出**：与输入同尺寸的 RGBA 像素缓冲区。

**正确性**：输出缓冲区与预计算参考值逐像素对比（容差：±1，因四舍五入所致）。

---

### 2.2 B2 — JSON 往返处理（浏览器）

#### 2.2.1 覆盖场景

浏览器端的 JSON 往返处理测试两个关键维度：

- **JS-Wasm 数据交换**：在真实浏览器 Wasm 应用中，结构化数据必须跨越 JS-Wasm 边界。此过程涉及内存复制、字符串编解码（UTF-8 ↔ UTF-16）以及缓冲区管理——这是公认的性能瓶颈 [R4]。
- **动态内存分配模式**：JSON 解析需要频繁的内存分配与释放，恰好是 GC 模型（Go）与所有权模型（Rust）差异最显著之处。
- **文本处理**（占 Web 端 Wasm 二进制的 11%）：Web 上部署最广泛的 Wasm 二进制是 Hyphenopoly（一个文本处理库，出现在 34.9% 使用 Wasm 的域名上）[R5]。JSON 解析与文本处理具有相同的字符串操作和内存分配模式。

**预估覆盖率**：直接覆盖约 15%–20% 的浏览器端 Wasm 用例；其所测试的 JS-Wasm 数据交换模式对几乎所有与 JavaScript 交互的浏览器 Wasm 应用均有广泛适用性。

#### 2.2.2 设计理由

1. JSON 是 Web 数据交换的通用格式。任何从 JavaScript 接收输入或向 JavaScript 返回结果的浏览器 Wasm 模块，都可能处理 JSON 式的结构化数据。
2. 操作包含**反序列化 + 业务逻辑（过滤和排序）+ 序列化**，代表了一个真实的端到端数据处理流水线，而非合成的微基准测试。
3. 使用与 B4（WASI 场景）**完全相同的数据和逻辑**，可实现直接的跨场景对比。

#### 2.2.3 规格定义

**输入**：一个 JSON 字符串，包含 `N` 条用户记录的数组。每条记录的模式如下：

```json
{
  "id": <int>,
  "name": "<string>",
  "email": "<string>",
  "age": <int>,
  "score": <float64>
}
```

记录以确定性方式生成：`id` 从 1 开始递增；`name`、`email`、`age`、`score` 由**固定种子 42** 的 PRNG 派生。

- `name`：8–16 个随机小写 ASCII 字符。
- `email`：`<name>@example.com`。
- `age`：`[10, 80]` 范围内的随机整数。
- `score`：`[0.0, 100.0]` 范围内的随机浮点数，保留 2 位小数。

**规模**：N = `100`、`1,000`、`10,000`。

**操作**：
1. **反序列化**：将 JSON 字符串解析为类型化结构体/对象数组。
2. **过滤**：仅保留 `age >= 18` 的记录。
3. **排序**：按 `score` **降序**排列。分数相同时按 `id` **升序**排列（确保输出确定性）。
4. **序列化**：将结果数组重新编码为 JSON 字符串。

**输出**：JSON 字符串。

**正确性**：输出 JSON 与预计算参考值进行语义级比较验证（解析后的数据结构必须相等；详见第 4.4 节关于字节级匹配不充分的说明）。

---

### 2.3 B3 — SHA-256 哈希（微服务 / WASI）

#### 2.3.1 覆盖场景

SHA-256 哈希代表了微服务 / Serverless 环境中常见的**纯计算密集型整数运算**模式：

- **认证与签名**：API 网关、JWT 验证、HMAC 计算。
- **数据完整性**：内容寻址存储、缓存校验、校验和验证。
- **密码学运算**：一项 2025 年的对比研究确认密码学运算是公认的、有代表性的 Wasm 工作负载类别 [R6]。

在 WASI/Serverless 场景中，纯计算函数正是 Wasm 相比容器优势最大之处：镜像体积缩小最多 30 倍，冷启动延迟降低最多 16% [R7]。

**预估覆盖率**：约 30%–40% 的计算密集型微服务 Wasm 函数。

#### 2.3.2 设计理由

1. 选择 SHA-256 而非其他哈希函数，因其在 Go 标准库（`crypto/sha256`）和 Rust 生态（`sha2` crate）中均有广泛可用的实现，确保使用惯用的、生产级的代码进行公平对比。
2. 编译为 Wasm 后，Go 和 Rust 均无法使用 CPU 特定的密码学指令集扩展（如 SHA-NI、AES-NI），因此双方都回退到纯软件实现——在算法和编译器优化层面的对比是公平的。
3. SHA-256 属于**整数运算密集型**（32 位加法、循环移位、位运算），与 B1 的浮点密集型和 B2/B4 的分配密集型形成互补。

#### 2.3.3 规格定义

**输入**：大小为 `S` 的字节缓冲区，以重复模式 `0x00, 0x01, 0x02, ..., 0xFF, 0x00, 0x01, ...` 填充（确定性生成，无需 PRNG）。

**规模**：S = `1 KB`（1,024 字节）、`64 KB`（65,536 字节）、`1 MB`（1,048,576 字节）、`16 MB`（16,777,216 字节）。

**操作**：计算输入缓冲区的 SHA-256 摘要。

**实现**：使用各语言的标准/规范库：
- Go：`crypto/sha256`
- TinyGo：`crypto/sha256`（相同 API，TinyGo 兼容子集）
- Rust：`sha2` crate（`sha2::Sha256`）

**输出**：32 字节（256 位）摘要，十六进制编码。

**正确性**：输出摘要与各输入规模的预计算参考值进行验证。参考值可使用 `sha256sum` 命令独立验证。

---

### 2.4 B4 — JSON 往返处理（微服务 / WASI）

#### 2.4.1 覆盖场景

JSON 序列化/反序列化是 Wasm 微服务中**最主要的数据交换瓶颈**：

- Roadrunner 项目（arXiv, 2024）发现 Wasm Serverless 工作流中 **97% 的数据传输**涉及序列化开销，仅优化这一环节即可实现 44–89% 的延迟降低和 69 倍的吞吐量提升 [R8]。
- Lumos 基准测试研究（ACM IoT 2025）指出，I/O 序列化在解释执行的 Wasm 中造成高达 10 倍的开销，在 AOT 编译的 Wasm 中也有最多 2 倍的开销 [R7]。

**预估覆盖率**：微服务 Wasm 数据处理模式的 70% 以上（因为几乎所有 Serverless 函数都涉及 JSON 输入输出）。

#### 2.4.2 设计理由

1. 基于研究证据，JSON 处理是最具代表性的单一微服务工作负载。
2. 使用与 B2（浏览器场景）**完全相同的数据、模式和操作逻辑**，可实现独特的**跨场景对比**：相同计算在两种不同的 Wasm 环境（浏览器 JS 引擎 vs Wasmtime）中运行。
3. 在 WASI 上下文中不存在 JS-Wasm 交互开销；数据通过 **stdin** 传入、结果通过 **stdout** 输出，隔离了纯 JSON 处理性能。

#### 2.4.3 规格定义

**与 B2（第 2.2.3 节）相同**，仅有以下差异：

- **输入传递方式**：JSON 字符串通过 **stdin**（WASI 文件描述符）读取。
- **输出传递方式**：结果 JSON 字符串写入 **stdout**。
- **无 JS-Wasm 交互**：数据全程在 Wasm 线性内存中处理。

---

## 3. 度量指标

### 3.1 编译指标

| 编号 | 指标 | 方法 | 单位 |
|------|------|------|------|
| C1 | 二进制体积 | 使用标准优化选项编译后的 `.wasm` 文件大小 | 字节 |
| C2 | 构建时间 | 5 次连续**清洁构建**（每次构建前清除缓存）的中位数 | 秒 |

**优化选项**：
- Go：`-ldflags="-s -w"`（去除符号表和调试信息）
- TinyGo：`-opt=z -no-debug`
- Rust：`--release`，配合 `[profile.release] opt-level = "z"`, `lto = true`, `strip = true`, `codegen-units = 1`

### 3.2 浏览器运行时指标

| 编号 | 指标 | 方法 | 单位 |
|------|------|------|------|
| R1 | 模块实例化时间 | 从 `WebAssembly.instantiateStreaming()` 调用到 Promise 解决的挂钟时间 | ms |
| R2 | 执行时间 | 使用 `performance.now()` 对内核调用计时；**5 次预热**后 **30 次迭代**的均值 | ms |
| R3 | 内存增量 | 首次运行前和末次运行后采样 `performance.measureUserAgentSpecificMemory()`，报告差值 | 字节 |

### 3.3 WASI 运行时指标

| 编号 | 指标 | 方法 | 单位 |
|------|------|------|------|
| R4 | 冷启动时间 | 完整 `wasmtime run` 调用（进程启动到退出）；使用 `hyperfine --warmup 3 --runs 30` 测量 | ms |
| R5 | 执行时间 | Wasm 模块内部计时（clock_gettime 或等效 API）；**5 次预热**后 **30 次迭代**的均值 | ms |
| R6 | 峰值内存 | `/usr/bin/time -l`（macOS）或 `/usr/bin/time -v`（Linux）报告的最大常驻集大小 | 字节 |

### 3.4 工程指标

| 编号 | 指标 | 方法 | 单位 |
|------|------|------|------|
| E1 | 源代码行数 | 使用 `cloc` 统计，排除注释和空行；仅计入基准测试实现文件 | 行 |
| E2 | 工具链复杂度 | 对构建步骤、所需配置和依赖管理的定性评估 | — |

---

## 4. 测试流程

### 4.1 环境要求

- **硬件**：所有基准测试必须在**同一台物理机**上运行。记录：CPU 型号、核心数、时钟频率、内存大小。
- **操作系统**：macOS 或 Linux。记录：具体版本。
- **浏览器**：Google Chrome（最新稳定版）。记录：具体版本和 V8 版本。
- **WASI 运行时**：Wasmtime（最新稳定版）。记录：具体版本。
- **编译器**：记录 Go、TinyGo、Rust（rustc）、wasm-bindgen、wasm-pack 的具体版本。

### 4.2 浏览器场景流程

```
对每条工具链 T ∈ {Go, TinyGo, Rust}：
  对每个测试用例 B ∈ {B1, B2}：
    1. 清洁构建：移除所有构建产物
    2. 使用 T 编译 B，目标为浏览器 Wasm
    3. 记录 C1（二进制体积）和 C2（构建时间，重复 5 次，取中位数）
    4. 将 .wasm 文件与最小 HTML 测试框架一同部署
    5. 启动本地 HTTP 服务器（Node.js，设置 COOP/COEP 头以启用内存测量 API）
    6. 通过 Playwright 启动 Chromium（无头模式，一致的启动参数）
    7. 对每个输入规模 S：
       a. 加载 Wasm 模块 → 记录 R1（实例化时间）
       b. 运行 5 次预热迭代（丢弃结果）
       c. 运行 30 次测量迭代 → 记录 R2（每次迭代的执行时间）
       d. 记录 R3（内存增量）
       e. 捕获输出并与参考值验证正确性
    8. 将所有指标导出为 JSON
```

**Chrome 启动参数**（保证一致性）：
```
--disable-extensions --disable-background-networking
--disable-default-apps --no-first-run
--disable-gpu --js-flags="--no-opt"
```

注：`--js-flags="--no-opt"` **不影响** Wasm 本身的执行（Wasm 始终由 V8 的 TurboFan/Liftoff 编译）；它仅阻止 JavaScript JIT 优化对 JS 胶水代码计时的干扰。

### 4.3 WASI / 微服务场景流程

```
对每条工具链 T ∈ {Go, TinyGo, Rust}：
  对每个测试用例 B ∈ {B3, B4}：
    1. 清洁构建：移除所有构建产物
    2. 使用 T 编译 B，目标为 wasip1
    3. 记录 C1（二进制体积）和 C2（构建时间，重复 5 次，取中位数）
    4. 对每个输入规模 S：
       a. 生成确定性测试输入文件（所有工具链共享）
       b. 冷启动测量：
          hyperfine --warmup 3 --runs 30 \
            'wasmtime run module.wasm < input_S.bin'
          → 记录 R4
       c. 暖执行测量：
          wasmtime run module.wasm --bench 35 < input_S.bin
          模块内部运行 5 次预热 + 30 次测量迭代，
          将每次迭代耗时输出到 stderr（stdout 承载实际输出）
          → 记录 R5
       d. 峰值内存测量：
          /usr/bin/time -l wasmtime run module.wasm < input_S.bin
          → 记录 R6（最大常驻集大小）
       e. 捕获输出并与参考值验证正确性
    5. 将所有指标导出为 JSON
```

### 4.4 正确性验证

在任何性能测量之前，**所有实现必须对所有输入规模产生相同的输出**：

1. 使用独立的生成器程序（`testdata/generate.go`）确定性地生成所有输入数据和参考输出。
2. 对每个（工具链 × 测试用例 × 输入规模）组合，将 Wasm 输出与参考值对比：
   - B1：逐像素对比，容差 ±1（因浮点取整）。
   - B2/B4：**语义级 JSON 比较**——分别解析两份输出并比较数据结构。此方式可消除 Go 与 Rust 之间的序列化差异（例如，Go 的 `encoding/json` 将 `95.0` 序列化为 `95`，而 Rust 的 `serde_json` 保留 `95.0`）。
   - B3：十六进制摘要精确匹配。
3. 任何不匹配均为**阻断性错误**——必须先修复实现，再进行性能测量。

---

## 5. 统计分析

### 5.1 数据报告

对每项指标报告：
- **均值**、**中位数**、**标准差**、**最小值**、**最大值**。
- 样本数：运行时指标 N = 30，构建时间 N = 5。

### 5.2 可视化

- **箱线图**：各工具链执行时间分布（R2、R4、R5）。
- **柱状图**：二进制体积（C1）和构建时间（C2）。
- **折线图**：执行时间随输入规模变化的趋势，展示可扩展性。
- **散点图**：跨场景对比（浏览器 vs WASI），用于相同工作负载的环境差异分析。
- **雷达图**：基于 min-max 归一化的多维综合评估（C1、C2、R1–R6、E1、E2）。

### 5.3 显著性检验

- 使用 **Mann-Whitney U 检验**（非参数检验，不假设正态分布）判断工具链之间的性能差异是否具有统计显著性。
- 显著性水平：α = 0.05（*）、α = 0.01（**）、α = 0.001（***）。
- 报告每对比较的 p 值（Go vs Rust、TinyGo vs Rust、Go vs TinyGo）。

---

## 6. 参考资料

- **[R1]** Figma Blog. "WebAssembly cut Figma's load time by 3x." 2017. https://www.figma.com/blog/webassembly-cut-figmas-load-time-by-3x/
- **[R2]** Jangda, A., Powers, B., Berger, E., Guha, A., & Larus, J. "Not So Fast: Analyzing the Performance of WebAssembly vs. Native Code." USENIX ATC, 2019. https://www.usenix.org/conference/atc19/presentation/jangda
- **[R3]** "Performance evaluation of image convolution with WebAssembly." SPIE Proceedings, Vol. 12592, 2023. https://doi.org/10.1117/12.2667004
- **[R4]** Haas, A., Rossberg, A., Schuff, D. L., Titzer, B. L., et al. "Bringing the Web up to Speed with WebAssembly." PLDI, 2017. https://doi.org/10.1145/3062341.3062363
- **[R5]** Hilbig, A., Lehmann, D., & Pradel, M. "An Empirical Study of Real-World WebAssembly Binaries: Security, Languages, Use Cases." WWW, 2021. https://doi.org/10.1145/3442381.3450138
- **[R6]** "Evaluating Legacy and Modern Cryptography on the Web: RSA, Hybrid AES and Ed25519 in Wasm and JavaScript." Journal of Communications, Vol. 20, No. 6, 2025. https://www.jocm.us/show-321-2118-1.html
- **[R7]** Korvoj, M. et al. "Lumos: Performance Characterization of WebAssembly as a Serverless Runtime in the Edge-Cloud Continuum." arXiv:2510.05118, 2024. https://arxiv.org/abs/2510.05118
- **[R8]** "Roadrunner: Improving the Serverless Forwarding Layer for WebAssembly." arXiv:2511.01888, 2024. https://arxiv.org/abs/2511.01888
- **[R9]** Scott Logic. "The State of WebAssembly 2023." https://blog.scottlogic.com/2023/10/18/the-state-of-webassembly-2023.html
- **[R10]** WebAssembly Community Group. "WebAssembly Core Specification." https://webassembly.org/
