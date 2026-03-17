# Go 与 Rust 在 WebAssembly 应用开发中的对比研究

> **说明**：本文档为论文初稿全文（第 1–7 章）。引用标记 `[n]` 对应文末参考文献列表。

---

## 摘要

WebAssembly（Wasm）作为 W3C 标准的可移植二进制指令格式，已在浏览器端高性能计算和基于 WASI 的微服务场景中获得广泛应用。Go 和 Rust 是 WebAssembly 生态中最受关注的两种系统级编程语言，但目前缺少在统一实验框架下对两者进行系统性对比的研究。本文设计并实现了一套涵盖浏览器端和 WASI 微服务端的基准测试方案，选取图像卷积、JSON 往返处理、SHA-256 哈希三类代表性工作负载共四个测试用例，分别使用 Go 标准编译器、TinyGo 和 Rust 三条工具链编译为 WebAssembly 模块，从编译特性（二进制体积、构建时间）、运行性能（实例化时间、执行时间、内存占用）和工程效率（代码行数、工具链复杂度）三个维度进行量化对比，并采用 Mann-Whitney U 检验验证差异的统计显著性。实验结果表明：Rust 产物体积最小（平均约 78 KB），在数据处理场景中执行速度领先 Go 3–33 倍、TinyGo 4–10 倍，且内存效率最优；TinyGo 借助 LLVM 后端优化，在计算密集型场景的执行时间上多数配置下优于 Rust 约 6%–11%，但其保守式垃圾回收导致内存占用极高（最高达 Rust 的约 40 倍）；Go 标准编译器工具链最为简洁，但产物体积最大（平均约 2.7 MB）且执行性能整体最慢。本文基于实验数据和生态成熟度分析，为不同应用场景下的 WebAssembly 语言与工具链选型提供了量化参考依据。

**关键词：** WebAssembly；Go；Rust；TinyGo；性能基准测试；WASI；浏览器；工具链对比

## Abstract

WebAssembly (Wasm), a W3C-standardized portable binary instruction format, has been widely adopted for high-performance computation in browsers and microservice workloads via the WebAssembly System Interface (WASI). Go and Rust are among the most prominent systems programming languages targeting WebAssembly, yet a systematic comparison under a unified experimental framework remains lacking. This thesis designs and implements a benchmark suite spanning both browser and WASI environments, comprising four test cases across three representative workload types: image convolution (compute-intensive), JSON round-trip processing (data-intensive), and SHA-256 hashing (integer-compute-intensive). Each test case is compiled to WebAssembly using three toolchains — the Go standard compiler, TinyGo, and Rust — and evaluated along three dimensions: compilation characteristics (binary size, build time), runtime performance (instantiation time, execution time, memory usage), and engineering efficiency (source lines of code, toolchain complexity). Statistical significance is assessed using the Mann-Whitney U test. Results show that Rust produces the smallest binaries (~78 KB on average) and achieves 3–33× faster execution than Go and 4–10× faster than TinyGo in data-processing workloads, with the lowest memory footprint. TinyGo, leveraging its LLVM backend, outperforms Rust by approximately 6%–11% in execution time for most compute-intensive configurations, but its conservative garbage collector incurs extremely high memory consumption (up to ~40× that of Rust). The Go standard compiler offers the simplest toolchain but produces the largest binaries (~2.7 MB on average) and is generally the slowest in execution. Based on the experimental data and an analysis of ecosystem maturity, this thesis provides quantitative guidance for WebAssembly language and toolchain selection across different application scenarios.

**Keywords:** WebAssembly; Go; Rust; TinyGo; performance benchmarking; WASI; browser; toolchain comparison

---

## 第 1 章 绪论

### 1.1 研究背景

随着 Web 应用从简单的文档呈现演变为复杂的交互式平台，前端应用对计算性能的需求持续增长。传统的 JavaScript 虽然凭借 V8、SpiderMonkey 等现代引擎的即时编译（JIT）技术取得了显著的性能提升，但其动态类型特性和垃圾回收机制使其在计算密集型任务中仍存在固有的性能瓶颈。与此同时，云原生与边缘计算的兴起对服务端应用提出了更轻量、更快启动、更强隔离性的要求，传统容器化方案在冷启动延迟和资源开销方面面临挑战。

在此背景下，WebAssembly（简称 Wasm）应运而生。WebAssembly 是一种低级的、紧凑的二进制指令格式，最初由 W3C 社区组提出，旨在为 Web 提供一种接近原生性能的可移植编译目标 [1]。2017 年 2 月，Chrome、Firefox、Edge 和 Safari 四大浏览器厂商达成共识，WebAssembly 的初始 API 和二进制格式设计完成，浏览器开始默认启用 WebAssembly 支持 [2]。2019 年 12 月 5 日，WebAssembly 核心规范正式成为 W3C 推荐标准，标志着它与 HTML、CSS、JavaScript 并列成为 Web 的第四种官方语言 [3]。

WebAssembly 的应用范围已远超浏览器。随着 WebAssembly 系统接口（WASI）的提出和发展 [4]，Wasm 模块可以在非浏览器环境中运行，涵盖 Serverless 函数、边缘计算节点、插件系统等场景。Scott Logic 的 State of WebAssembly 2023 调查显示，WebAssembly 的 Serverless 使用率已达约 40%，插件环境使用率约 30%，且均呈逐年增长趋势 [5]。WASI Preview 2（WASI 0.2）于 2024 年 1 月正式发布，引入了基于"世界"（worlds）的接口体系，包括 wasi-cli、wasi-http、wasi-filesystem 和 wasi-sockets 等标准化接口 [6]，进一步推动了 WebAssembly 在服务端和边缘场景中的应用。

在规范演进层面，WebAssembly 技术在 2023 年取得了多项关键突破 [31]。WebAssembly GC（垃圾回收）提议和 Typed Function References 提议均进入标准化阶段（Phase 4），使 TypeScript、Kotlin、Java 等需要 GC 支持的高级语言能够更高效地编译至 Wasm，无需将语言虚拟机一同打包，从而显著减小了产物体积并提升了运行性能。Component Model（组件模型）提议也获得了社区的广泛支持，旨在解决多语言环境下 Wasm 模块间的互操作与数据共享问题；基于组件模型重新设计的 WASI Preview 2 正式上线。此外，Memory64、Multi-Memories、Exception Handling 等提议持续推进，wasi-threads 为 WASI 环境引入了多线程支持，wasi-nn 则为机器学习推理提供了标准化接口。这些进展表明 WebAssembly 正从浏览器沙箱中的性能加速器，发展为覆盖云原生、边缘计算、人工智能等广泛领域的通用计算平台 [31][32]。

在编程语言支持方面，WebAssembly 作为编译目标可接受多种源语言。Hilbig 等人对 8,461 个真实世界 Wasm 二进制文件的大规模实证研究表明，C/C++、Rust 和 Go 是最主要的 Wasm 源语言，其中约三分之二的二进制文件来源于 C/C++ 等非内存安全语言 [7]。在众多可编译至 WebAssembly 的语言中，Go 和 Rust 因兼具系统级性能与现代语言特性而备受关注：Go 以简洁的语法、内置并发原语和成熟的标准库著称，在云原生领域有广泛应用；Rust 以零成本抽象、所有权系统和无垃圾回收器的内存安全保障为特色，在系统编程和性能敏感场景中表现突出。两种语言均已建立了各自的 WebAssembly 工具链生态：Go 自 1.11 版本起原生支持编译至 Wasm（`GOOS=js GOARCH=wasm`），自 1.21 版本起支持 WASI（`GOOS=wasip1`）[8]；TinyGo 作为 Go 的替代编译器专为嵌入式和 Wasm 场景优化 [9]；Rust 则于 2017 年底引入 `wasm32-unknown-unknown` 编译目标，并通过 wasm-bindgen [10] 和 wasm-pack 等工具提供了成熟的浏览器集成方案。

然而，目前学术界和工程实践中对 Go 与 Rust 在 WebAssembly 应用开发中的系统性对比研究尚不充分。既有研究多集中于 Wasm 与原生代码或 JavaScript 的性能比较 [11]，或针对单一语言的 Wasm 编译特性分析，缺少在统一实验环境下对两种语言在 Wasm 开发全流程——编译产物、运行性能、开发效率——进行全面对比的工作。

### 1.2 研究目的与意义

本文旨在对 Go 与 Rust 在 WebAssembly 应用开发中的表现进行系统性对比研究，通过设计统一的实验环境和代表性测试用例，从编译特性、运行性能和工程效率三个维度进行量化分析，为实际项目中的 WebAssembly 技术选型提供科学依据。

**理论意义**：本研究有助于深入理解两种不同内存管理范式（Go 的垃圾回收 vs Rust 的所有权系统）在 WebAssembly 虚拟机上的性能表现差异，揭示语言设计决策对 Wasm 编译产物质量和运行效率的影响机制。

**实践意义**：通过浏览器端和微服务两类典型场景的实验验证，本研究的结论可直接指导开发团队在 WebAssembly 项目中选择合适的编程语言和工具链。根据 Scott Logic 的调查数据，2023 年已有 41% 的受访者在生产环境中使用 WebAssembly [5]，技术选型建议具有较强的现实需求。

### 1.3 国内外研究现状

#### 1.3.1 WebAssembly 性能研究

WebAssembly 的性能特性是学术界关注的焦点。Haas 等人在 PLDI 2017 上发表的奠基性论文 [1] 定义了 WebAssembly 的核心语义和类型系统，并证明了其可执行性和类型安全性。Jangda 等人 [11] 在 USENIX ATC 2019 上发表了迄今最全面的 Wasm 与原生代码性能对比研究，使用 SPEC CPU 基准套件发现 Wasm 应用在 Firefox 上平均比原生代码慢 45%、在 Chrome 上慢 55%，远高于早期研究报告的 10% 差距。该研究揭示了性能差距的主要来源包括更多的寄存器溢出（spilling）、更多的分支指令以及间接寻址操作。

在 Wasm 运行时层面，Korvoj 等人的 Lumos 研究 [12] 对 WebAssembly 作为 Serverless 运行时的性能进行了系统刻画，发现 AOT 编译的 Wasm 镜像比容器小最多 30 倍，冷启动延迟降低最多 16%，但解释执行的 Wasm 暖延迟高达容器的 55 倍。

#### 1.3.2 WebAssembly 生态与应用研究

Hilbig 等人 [7] 对 8,461 个真实 Wasm 二进制文件的研究是目前规模最大的 Wasm 生态实证分析，揭示了 Web 端 Wasm 的实际用例分布：游戏（25%）、文本处理（11%）、可视化/动画（11%）、媒体处理（9%）等。该研究还发现曾经占主导地位的加密挖矿已降至不足 1%，Wasm 生态正朝着多元化方向发展。

在 Serverless 场景中，Roadrunner 项目 [13] 的研究发现 Wasm Serverless 工作流中 97% 的数据传输涉及序列化开销，优化 JSON 序列化可实现 44–89% 的延迟降低和 69 倍的吞吐量提升，凸显了数据序列化在 Wasm 微服务中的关键地位。

在工业实践方面，WebAssembly 已在多个领域获得规模化应用。Figma 将其 C++ 渲染引擎编译为 Wasm，使页面加载时间降低 3 倍 [32]；Adobe Photoshop Web 版利用 Wasm 实现了浏览器中的专业级图像处理；AutoCAD、Google Earth 等桌面应用也借助 Wasm 完成了向 Web 平台的迁移。2022 年，Docker 宣布支持 WebAssembly 工作负载，与 WasmEdge 合作构建了 containerd shim，使开发者可以像运行容器一样运行 Wasm 应用 [32]，标志着 WebAssembly 在云原生基础设施中的地位获得了行业巨头的认可。这一系列实践充分说明 WebAssembly 已从实验性技术进入生产就绪阶段，其性能、可移植性和安全隔离特性使之成为跨平台应用开发的重要基础设施。

#### 1.3.3 Go 与 Rust 的 Wasm 支持研究

关于 Go 与 Rust 的 Wasm 编译特性，现有研究相对分散。Karnwong 的基准测试 [14] 对比了 Go、Python 和 Rust 编译至 Wasm 的性能，发现 Rust 编译的 Wasm 相比原生代码的性能衰减最小（仅 0.003 秒开销）。在密码学领域，JoCM 2025 的研究 [15] 评估了 RSA、AES 和 Ed25519 在 Wasm 与 JavaScript 中的性能，发现 Wasm 在解密和签名任务中表现优异。然而，目前尚未见到在统一框架下对 Go（含 TinyGo）与 Rust 在浏览器端和微服务端两个场景中进行全面对比的研究。

### 1.4 研究内容与技术路线

本文的研究内容包括以下几个方面：

1. **理论调研**：系统梳理 WebAssembly 的核心原理、运行机制及其在浏览器和 WASI 两种环境下的执行流程；深入研究 Go（标准编译器和 TinyGo）、Rust 对接 WebAssembly 的技术体系和编译部署流程。

2. **实验设计**：搭建统一的实验环境，选取两类典型应用场景（浏览器端和微服务端），每个场景设计两个功能一致的测试用例——浏览器端选取图像卷积（计算密集型）和 JSON 往返处理（数据处理型）；微服务端选取 SHA-256 哈希（计算密集型）和 JSON 往返处理（数据处理型）。

3. **对比实验**：分别使用 Go 标准编译器、TinyGo 和 Rust 实现所有测试用例，在统一环境下采集编译产物体积、构建时间、运行执行时间、冷启动延迟、内存占用等指标数据。

4. **分析评价**：运用统计分析方法（包括描述性统计和 Mann-Whitney U 显著性检验）对实验数据进行对比分析，结合工程指标（代码行数、工具链复杂度）对两种语言在 WebAssembly 开发中的适用性进行综合评估。

技术路线如下图所示：

```
理论调研          实验设计           实验实施          分析与总结
   │                │                  │                 │
   ├─ Wasm 原理     ├─ 环境搭建        ├─ Go 实现        ├─ 数据分析
   ├─ Go/Rust 生态  ├─ 用例设计        ├─ TinyGo 实现    ├─ 显著性检验
   └─ 文献综述      └─ 指标定义        ├─ Rust 实现      └─ 结论建议
                                      └─ 数据采集
```

### 1.5 论文组织结构

本文共分为七章，各章内容安排如下：

- **第 1 章 绪论**：阐述研究背景、研究目的与意义、国内外研究现状、研究内容与技术路线。
- **第 2 章 相关技术基础**：介绍 WebAssembly 核心原理、运行机制，以及 Go 和 Rust 对接 WebAssembly 的技术体系。
- **第 3 章 实验环境与系统总体设计**：说明实验环境搭建、评价指标体系、测试用例设计及示例系统总体架构。
- **第 4 章 基于 Go 的 WebAssembly 应用实现**：详细说明 Go 标准编译器和 TinyGo 编译至 Wasm 的实现过程。
- **第 5 章 基于 Rust 的 WebAssembly 应用实现**：详细说明 Rust 编译至 Wasm 的实现过程。
- **第 6 章 实验测试与性能对比分析**：展示实验数据，进行性能对比和综合分析。
- **第 7 章 总结与展望**：总结研究成果，提出技术选型建议和未来工作方向。

---

## 第 2 章 相关技术基础

### 2.1 WebAssembly 核心原理

#### 2.1.1 WebAssembly 概述

WebAssembly（Wasm）是一种面向栈式虚拟机设计的二进制指令格式 [1]。它被设计为高级语言的可移植编译目标，能够在 Web 和非 Web 环境中以接近原生的速度执行。WebAssembly 的设计目标包括：快速、安全、可调试、可移植以及开放标准 [16]。

与 JavaScript 的文本格式不同，WebAssembly 采用紧凑的二进制编码，模块可以被高效地传输和解码。根据 Haas 等人的形式化定义 [1]，WebAssembly 的核心特性包括：

- **类型安全**：所有指令和函数签名在编译时经过类型检查，运行时不会出现类型错误。
- **内存安全**：线性内存通过边界检查实现隔离，Wasm 模块无法访问宿主内存空间。
- **确定性执行**：在给定相同输入的条件下，Wasm 程序的执行结果是确定的（除浮点 NaN 位模式外）。

#### 2.1.2 模块结构

一个 WebAssembly 模块由以下核心组成部分构成 [16]：

- **类型段（Type Section）**：定义模块中所有函数签名的类型。
- **函数段（Function Section）**：将函数索引映射到类型签名。
- **内存段（Memory Section）**：声明模块使用的线性内存，以页（64 KB）为单位。
- **全局段（Global Section）**：定义全局变量及其可变性。
- **导出段（Export Section）**：声明模块向宿主环境暴露的函数、内存、表和全局变量。
- **导入段（Import Section）**：声明模块从宿主环境引入的外部函数和资源。
- **代码段（Code Section）**：包含所有函数体的字节码指令。
- **数据段（Data Section）**：用于初始化线性内存中的数据。

#### 2.1.3 线性内存模型

WebAssembly 采用线性内存模型，每个模块实例拥有一块连续的、可按字节寻址的内存空间 [1]。线性内存的初始大小和最大大小在模块定义中声明，运行时可通过 `memory.grow` 指令动态扩展。

线性内存与宿主环境内存完全隔离，Wasm 代码只能通过导入的宿主函数或共享内存方式与外部交互。这种隔离机制是 WebAssembly 安全沙箱的核心基础。对于 Go 和 Rust 编译至 Wasm 的程序，线性内存同时承载栈帧和堆分配，两种语言的内存管理策略（垃圾回收 vs 手动管理/所有权系统）在此受限环境中的表现差异是本文的重要研究内容之一。

#### 2.1.4 指令集概述

WebAssembly 指令集基于栈式虚拟机模型，包含以下主要类别 [16]：

- **数值指令**：整数和浮点数的算术运算（加、减、乘、除）、比较运算和类型转换。支持 i32、i64、f32、f64 四种基本数值类型。
- **内存指令**：线性内存的读写操作（`load`/`store`），支持多种宽度和符号扩展。
- **控制流指令**：结构化控制流（`block`、`loop`、`if`/`else`）和分支指令（`br`、`br_if`、`br_table`）。
- **变量指令**：局部变量和全局变量的读写。
- **表指令**：间接函数调用和表操作。

### 2.2 WebAssembly 运行机制

#### 2.2.1 浏览器端运行流程

在浏览器环境中，WebAssembly 模块的加载和执行遵循以下流程：

1. **获取（Fetch）**：通过网络请求获取 `.wasm` 二进制文件。
2. **编译（Compile）**：浏览器引擎将二进制字节码编译为目标平台的机器码。现代浏览器通常采用两级编译策略：先用基线编译器（如 V8 的 Liftoff）快速生成未优化代码以减少启动延迟，再用优化编译器（如 V8 的 TurboFan）在后台生成高性能代码。
3. **实例化（Instantiate）**：创建模块实例，分配线性内存，导入宿主函数，执行数据段初始化。
4. **执行（Execute）**：JavaScript 通过导出函数调用 Wasm 代码，Wasm 也可通过导入函数回调 JavaScript。

浏览器提供了 `WebAssembly.compile()`、`WebAssembly.instantiate()` 和 `WebAssembly.instantiateStreaming()` 等标准 API [16]。其中 `instantiateStreaming()` 允许在下载的同时进行编译，是推荐的加载方式。

#### 2.2.2 WASI 运行环境

WebAssembly 系统接口（WASI）为 Wasm 模块提供了一套与操作系统交互的标准化 API，使其能够在浏览器之外的环境中运行 [4]。WASI 的设计遵循能力安全（capability-based security）原则，模块只能访问显式授予的资源。

WASI Preview 1（wasip1）提供了类 POSIX 的基本系统调用接口，包括文件系统访问、标准输入输出、环境变量和命令行参数等。WASI Preview 2（WASI 0.2）于 2024 年 1 月发布 [6]，引入了基于 WebAssembly 组件模型的现代接口体系。

主要的 WASI 运行时包括：

- **Wasmtime** [17]：由字节码联盟（Bytecode Alliance）维护，是最成熟的 WASI 运行时之一，支持 AOT 编译和组件模型。
- **Wasmer**：支持多种编译后端（Singlepass、Cranelift、LLVM），提供跨平台兼容性。
- **WasmEdge**：面向边缘计算和 AI 推理的轻量级运行时。

本文的微服务场景实验选用 Wasmtime 作为统一运行时。

### 2.3 Go 语言与 WebAssembly

#### 2.3.1 Go 标准编译器的 Wasm 支持

Go 语言自 1.11 版本（2018 年 8 月）起正式支持编译至 WebAssembly。通过设置环境变量 `GOOS=js GOARCH=wasm`，Go 标准编译器可将 Go 程序编译为在浏览器中运行的 `.wasm` 模块 [8]。该模式下，编译产物需配合 Go 官方提供的 `wasm_exec.js` 胶水文件在浏览器中加载和运行。

Go 1.21（2023 年 8 月）新增了对 WASI Preview 1 的实验性支持 [18]，开发者可通过 `GOOS=wasip1 GOARCH=wasm` 编译出可在 Wasmtime 等 WASI 运行时上执行的模块。该版本同时引入了 `go:wasmimport` 指令，允许 Go 代码导入宿主环境函数。

Go 编译至 Wasm 时，完整的 Go 运行时（包括 goroutine 调度器和垃圾回收器）会被嵌入编译产物中。这意味着即使是简单的程序，其 Wasm 二进制文件也包含了运行时开销，通常在数 MB 级别。

#### 2.3.2 TinyGo

TinyGo 是面向微控制器和 WebAssembly 等资源受限环境的 Go 替代编译器 [9]。与标准 Go 编译器不同，TinyGo 基于 LLVM 后端，通过存活性分析和死代码消除显著减小编译产物体积。

TinyGo 对 Wasm 的支持早于 Go 标准编译器的 WASI 支持。2023 年 8 月，TinyGo v0.29.0 新增了 `GOOS=wasip1` 支持 [19]，与 Go 1.21 的标准库实现对齐。TinyGo 编译的 Wasm 二进制文件通常比标准 Go 编译器的产物小一个数量级，但存在标准库兼容性方面的限制——部分 Go 标准库包（如 `reflect` 的完整功能）在 TinyGo 中不受支持。

优化编译选项对 TinyGo 的产物体积影响显著：使用 `-no-debug` 标志可去除调试符号，使用 `-opt=z` 可进一步优化体积。Fermyon 的工程实践表明，合理运用优化选项可将 TinyGo Wasm 模块体积减小约 60% [20]。

#### 2.3.3 Go Wasm 生态现状

Go 的 Wasm 生态相比 Rust 尚在发展中：

- **浏览器端**：通过 `syscall/js` 包实现与 JavaScript 的交互，可直接操作 DOM 和调用 Web API。
- **WASI 端**：标准库对 WASI 的支持仍处于实验阶段，部分 I/O 操作受限。
- **社区生态**：已有 Vugu（类 Vue 的 Go Web 框架）、Vecty 等项目探索基于 Go Wasm 的前端开发，但成熟度不及 Rust 生态。

### 2.4 Rust 语言与 WebAssembly

#### 2.4.1 Rust 的 Wasm 编译支持

Rust 对 WebAssembly 的支持始于 2017 年底，通过在 Rust 编译器中引入 `wasm32-unknown-unknown` 编译目标实现 [21]。该目标代表了"裸金属"式的 Wasm 支持，不依赖 Emscripten 工具链，直接将 Rust 代码编译为纯 WebAssembly 字节码。

Rust 编译至 Wasm 的主要编译目标包括：

- **`wasm32-unknown-unknown`**：面向浏览器和通用 Wasm 环境的目标，不假定任何系统接口。
- **`wasm32-wasip1`**（原 `wasm32-wasi`）：面向 WASI Preview 1 环境的目标，可使用标准输入输出、文件系统等系统接口。

由于 Rust 不依赖垃圾回收器，编译至 Wasm 时不会引入额外的运行时开销。Rust 的所有权系统和生命周期机制在编译阶段完成内存管理的验证，运行时不产生 GC 暂停。这使得 Rust 编译的 Wasm 模块通常具有更小的二进制体积和更可预测的性能特性。

#### 2.4.2 wasm-bindgen 与 wasm-pack

wasm-bindgen [10] 是 Rust WebAssembly 生态的基础设施项目，创建于 2017 年 12 月。它提供了 Rust 与 JavaScript 之间零成本交互的桥梁，自动生成所需的胶水代码。基于 wasm-bindgen，Rust 社区进一步构建了：

- **js-sys**：ECMAScript 标准 API 的原始绑定。
- **web-sys**：Web API（DOM、Fetch、Canvas 等）的原始绑定。
- **wasm-pack**：一站式构建工具，集成编译、优化（wasm-opt）和 npm 包生成。

wasm-bindgen 采用属性宏（`#[wasm_bindgen]`）标注需要暴露给 JavaScript 的函数和类型，在编译时自动生成类型安全的绑定代码。截至目前，wasm-bindgen 项目已获得超过 9,000 个 GitHub 星标和 440 余名贡献者 [10]，是 Wasm 语言生态中最成熟的 JavaScript 互操作方案之一。

#### 2.4.3 Rust Wasm 生态现状

根据 State of WebAssembly 2023 调查 [5]，Rust 连续三年位居 WebAssembly 最常用语言首位。Rust 的 Wasm 生态已形成了较为完善的工具链：

- **前端框架**：Yew、Leptos、Dioxus 等框架提供了类 React 的组件化前端开发体验。
- **WASI 支持**：Rust 的 WASI 支持最为成熟，Wasmtime、Wasmer 等主流运行时本身也使用 Rust 编写。
- **优化工具**：wasm-opt（Binaryen 项目）可对编译产物进行进一步的体积和性能优化。
- **组件模型**：wit-bindgen 为 WebAssembly 组件模型提供 Rust 绑定生成。

### 2.5 本章小结

本章介绍了 WebAssembly 的核心原理、运行机制，以及 Go（标准编译器和 TinyGo）与 Rust 对接 WebAssembly 的技术体系。两种语言在 Wasm 开发中的关键差异可概括为：

| 维度 | Go（标准 / TinyGo） | Rust |
|------|---------------------|------|
| 内存管理 | 垃圾回收（嵌入 Wasm 产物） | 所有权系统（零运行时开销） |
| 编译产物体积 | 较大（标准）/ 中等（TinyGo） | 较小 |
| JS 互操作 | `syscall/js` + `wasm_exec.js` | wasm-bindgen + js-sys/web-sys |
| WASI 支持 | Go 1.21+ / TinyGo 0.29+ | 原生支持，生态最成熟 |
| 学习曲线 | 较低 | 较高（所有权、生命周期） |

这些差异构成了后续实验对比的技术基础。

---

## 第 3 章 实验环境与系统总体设计

### 3.1 实验环境搭建

#### 3.1.1 硬件环境

为确保实验结果的可比性和可复现性，所有基准测试均在同一台物理机上运行。实验期间关闭无关后台进程，避免资源竞争对测试结果的干扰。硬件配置如下：

- **处理器**：Apple M3 Max（ARM64 架构）
- **内存**：128 GB 统一内存
- **存储**：内置 NVMe SSD

#### 3.1.2 软件环境

| 类别 | 工具 / 软件 | 版本 |
|------|------------|------|
| 操作系统 | macOS (Apple Silicon) | 26.3.1 (Build 25D2128) |
| 浏览器 | Chromium (Playwright 内置) | 145.0.7632.6 |
| WASI 运行时 | Wasmtime | 33.0.0 |
| Go 编译器 | Go | 1.25.8 |
| TinyGo 编译器 | TinyGo | 0.40.1 (LLVM 20.1.1) |
| Rust 编译器 | rustc | 1.94.0 |
| Rust Wasm 工具 | wasm-bindgen | 0.2.114 |
| 自动化测试 | Playwright | 1.50.x |
| CLI 基准工具 | hyperfine | 1.19.0 |
| 代码统计 | cloc | 2.04 |

#### 3.1.3 环境一致性保障

为确保实验公平性，采取以下措施：

1. **统一运行时版本**：所有 WASI 测试使用同一版本的 Wasmtime，所有浏览器测试使用同一版本的 Chromium。
2. **一致的编译优化等级**：Go 使用 `-ldflags="-s -w"`（去除符号表和调试信息）；TinyGo 使用 `-opt=z -no-debug`；Rust 使用 `--release` 配合 `opt-level = "z"`, `lto = true`, `strip = true`, `codegen-units = 1`, `panic = "abort"`。这些选项均为各工具链在生产部署场景下的推荐配置。
3. **清洁构建**：每次编译前清除所有缓存和构建产物，确保测量的是完整构建时间。
4. **系统状态控制**：测试期间禁用不必要的系统服务和后台进程，减少系统噪声。

### 3.2 实验评价指标体系

本文从编译特性、运行性能和工程效率三个维度建立评价指标体系。

#### 3.2.1 编译指标

| 指标 | 含义 | 度量方法 |
|------|------|---------|
| 二进制体积（C1） | 编译产物 `.wasm` 文件的大小 | 直接测量文件字节数 |
| 构建时间（C2） | 从源代码到 `.wasm` 文件的清洁构建耗时 | 5 次连续清洁构建的中位数 |

编译产物体积直接影响 Web 场景中的网络传输时间和 Serverless 场景中的冷启动延迟。Lumos 的研究 [12] 表明，Wasm 镜像的体积优势（比容器镜像小最多 30 倍）是其在边缘部署场景中的核心竞争力。

#### 3.2.2 运行性能指标

**浏览器端指标**：

| 指标 | 含义 | 度量方法 |
|------|------|---------|
| 模块实例化时间（R1） | Wasm 模块从加载到可执行的耗时 | `WebAssembly.instantiateStreaming()` 调用到 Promise 解决的挂钟时间 |
| 执行时间（R2） | 单次计算内核的执行耗时 | `performance.now()` 计时，5 次预热后 30 次迭代的均值 |
| 内存增量（R3） | 执行前后的内存变化 | `performance.measureUserAgentSpecificMemory()` API |

**WASI 端指标**：

| 指标 | 含义 | 度量方法 |
|------|------|---------|
| 冷启动时间（R4） | Wasmtime 进程启动到程序结束的全过程耗时 | `hyperfine --warmup 3 --runs 30` |
| 执行时间（R5） | 计算内核本身的执行耗时（不含进程启动） | Wasm 模块内部使用各语言高精度计时 API（Go `time.Now()` / Rust `std::time::Instant`），5 次预热后 30 次迭代的均值 |
| 峰值内存（R6） | 运行期间的最大内存占用 | macOS 下 `/usr/bin/time -l`，Linux 下 `/usr/bin/time -v` |

选择 30 次迭代和 5 次预热的依据：30 次采样满足中心极限定理对样本量的基本要求，可用于非参数统计检验；5 次预热确保 JIT 编译（浏览器端）和缓存（WASI 端）达到稳态。

#### 3.2.3 工程指标

| 指标 | 含义 | 度量方法 |
|------|------|---------|
| 源代码行数（E1） | 实现相同功能所需的代码量 | `cloc` 统计，排除注释和空行 |
| 工具链复杂度（E2） | 构建配置和依赖管理的复杂程度 | 定性评估（构建步骤数、配置文件数、依赖项数） |

### 3.3 测试用例设计

#### 3.3.1 设计原则

测试用例的选取遵循以下原则：

1. **真实代表性**：每个测试用例均对应经实证研究证实的真实 Wasm 工作负载模式。
2. **功能同质性**：Go 和 Rust 实现相同的算法逻辑，使用相同的输入数据，产生相同的输出结果。
3. **负载互补性**：四个测试用例分别覆盖计算密集型（浮点运算、整数运算）和数据处理型（序列化、内存分配）两大负载模式。
4. **可扩展性**：每个测试用例设计多个输入规模，以观察性能随数据量的变化趋势。

下表汇总了四个测试用例的编号、场景及负载类型：

| 编号 | 测试用例 | 场景 | 负载类型 | 输入规模 |
|------|---------|------|---------|---------|
| B1 | 图像卷积 | 浏览器 | 计算密集 + 内存访问密集 | 4 种图像尺寸 × 2 种卷积核 |
| B2 | JSON 往返处理 | 浏览器 | 数据处理 + JS-Wasm 交互 | 3 种记录数 |
| B3 | SHA-256 哈希 | 微服务（WASI） | 纯计算密集（整数运算） | 4 种输入大小 |
| B4 | JSON 往返处理 | 微服务（WASI） | 数据序列化 / 反序列化 | 3 种记录数 |

#### 3.3.2 B1：图像卷积（浏览器）

**选取依据**：图像卷积选自 SPIE 2023 年发表的 WebAssembly 图像卷积性能评估研究 [22]，该研究直接验证了图像卷积作为浏览器端 Wasm 代表性基准的有效性。根据 Hilbig 等人的统计 [7]，媒体处理（9%）和可视化/动画（11%）合计占 Web 端 Wasm 用例的约 20%，加上游戏类用例（25%）中涉及的类似计算模式，图像卷积的计算模式可代表约 25%–35% 的浏览器端 Wasm 负载。实验同时测试 3×3 和 5×5 两种高斯卷积核，以观察算术密集度对性能差异的影响。

**输入**：RGBA 像素缓冲区（每像素 4 字节），像素值由固定种子 42 的伪随机数生成器确定性生成。测试 4 种图像尺寸：256×256、512×512、1024×1024、1920×1080。输入文件位于 `testdata/image_WxH.rgba`。

**操作**：对 R、G、B 三通道分别执行二维卷积（A 通道直接复制），边界采用零填充，输出像素值钳位至 [0, 255] 并四舍五入。使用两种归一化高斯卷积核：3×3 核（K3 = (1/16)·[[1,2,1],[2,4,2],[1,2,1]]）和 5×5 核（K5 = (1/256)·[[1,4,6,4,1],[4,16,24,16,4],[6,24,36,24,6],[4,16,24,16,4],[1,4,6,4,1]]）。

**输出**：与输入同尺寸的 RGBA 像素缓冲区。正确性验证：输出与预计算参考值逐像素对比，容差 ±1。

**对应源代码**：

| 工具链 | 算法实现 | 浏览器入口 | WASI 入口 |
|--------|---------|-----------|-----------|
| Go / TinyGo | `go/conv/conv.go`（`Convolve` 函数） | `go/cmd/conv-browser/main.go`（`syscall/js` 暴露 `wasmConvolve`） | `go/cmd/conv-wasi/main.go`（stdin/stdout） |
| Rust | `rust/shared/src/conv.rs`（`convolve` 函数） | `rust/conv-browser/src/lib.rs`（`#[wasm_bindgen]` 导出 `convolve`） | `rust/conv-wasi/src/main.rs`（stdin/stdout） |

Go/TinyGo 浏览器入口使用 `js.CopyBytesToGo` 和 `js.CopyBytesToJS` 实现像素缓冲区在 JS 与 Wasm 线性内存之间的复制；Rust 端由 wasm-bindgen 自动处理 `&[u8]` 到 `Uint8Array` 的转换。图像卷积同时提供 WASI 入口（命令行参数 `width height kernel_size`，stdin 读取像素缓冲区），用于 WASI 场景的跨场景参考测试。

#### 3.3.3 B2：JSON 往返处理（浏览器）

**选取依据**：JSON 往返处理在浏览器端主要测试 JS-Wasm 边界的数据交换效率。Web 上部署最广泛的 Wasm 二进制文件 Hyphenopoly 是一个文本处理库，出现在 34.9% 使用 Wasm 的域名上 [7]，与 JSON 处理共享相同的字符串操作和动态内存分配模式。该用例同时考验 GC 模型（Go）与所有权模型（Rust）在频繁内存分配场景下的表现差异。

**输入**：JSON 字符串，包含 N 条用户记录数组，每条记录含 `id`（整数）、`name`（字符串）、`email`（字符串）、`age`（整数）、`score`（浮点数）五个字段。记录由固定种子 42 的伪随机数生成器确定性生成。测试 3 种规模：N = 100、1,000、10,000。输入文件位于 `testdata/users_N.json`。

**操作**：(1) 反序列化 JSON 字符串为类型化结构体数组；(2) 过滤：仅保留 `age >= 18` 的记录；(3) 排序：按 `score` 降序排列，分数相同时按 `id` 升序排列（确保确定性输出）；(4) 序列化：将结果数组编码回 JSON 字符串。

**输出**：JSON 字符串。正确性验证：语义级 JSON 比较（解析后数据结构相等）。

**对应源代码**：

| 工具链 | 算法实现 | 浏览器入口 |
|--------|---------|-----------|
| Go / TinyGo | `go/jsonrt/jsonrt.go`（`Process` 函数） | `go/cmd/json-browser/main.go`（通过 `syscall/js` 暴露 `wasmJsonRoundtrip` 全局函数） |
| Rust | `rust/shared/src/jsonrt.rs`（`process` 函数） | `rust/json-browser/src/lib.rs`（通过 `#[wasm_bindgen]` 导出 `json_roundtrip` 函数） |

Go 使用标准库 `encoding/json` 进行序列化/反序列化；Rust 使用 `serde` + `serde_json` crate。浏览器端数据以字符串形式跨越 JS-Wasm 边界传递。

#### 3.3.4 B3：SHA-256 哈希（微服务 / WASI）

**选取依据**：SHA-256 哈希代表微服务中常见的纯计算密集型整数运算。JoCM 2025 的密码学评估研究 [15] 确认了密码学运算在 Wasm 中的代表性。在 Wasm 运行时中，由于无法使用 CPU 的密码学指令集扩展（SHA-NI 等），Go 和 Rust 均回退到纯软件实现，保证了对比的公平性。SHA-256 以 32 位加法、循环移位和位运算为主，与 B1 的浮点密集型和 B2/B4 的分配密集型形成互补。

**输入**：大小为 S 的字节缓冲区，以重复模式 `0x00, 0x01, ..., 0xFF, 0x00, 0x01, ...` 填充。测试 4 种规模：S = 1 KB、64 KB、1 MB、16 MB。输入文件位于 `testdata/sha256_input_SIZE.bin`。

**操作**：计算输入缓冲区的 SHA-256 摘要。各语言使用标准/规范库：Go / TinyGo 使用 `crypto/sha256`；Rust 使用 `sha2` crate（`sha2::Sha256`）。

**输出**：32 字节摘要的十六进制字符串。正确性验证：与预计算参考值精确匹配。

**对应源代码**：

| 工具链 | 算法实现 | WASI 入口 |
|--------|---------|-----------|
| Go / TinyGo | `go/sha/sha.go`（`Sum256Hex` 函数） | `go/cmd/sha-wasi/main.go`（stdin 读取输入，stdout 输出摘要） |
| Rust | `rust/shared/src/sha.rs`（`sum256_hex` 函数） | `rust/sha-wasi/src/main.rs`（stdin 读取输入，stdout 输出摘要） |

WASI 入口程序支持 `--bench N` 参数启用内部计时模式：前 5 次迭代为预热，后 N−5 次为测量迭代，每次迭代耗时输出到 stderr。

#### 3.3.5 B4：JSON 往返处理（微服务 / WASI）

**选取依据**：JSON 序列化/反序列化是 Wasm 微服务中最关键的性能瓶颈。Roadrunner 项目 [13] 发现 97% 的 Serverless 数据传输涉及序列化开销，优化此环节可实现 44–89% 的延迟降低。B4 与 B2 使用完全相同的数据、模式和操作逻辑，但数据通过 WASI stdin/stdout 传递（非 JS-Wasm 边界），可隔离测试纯 JSON 处理性能，同时与 B2 形成跨场景对比。

**输入**：与 B2 相同的 JSON 用户记录数组，通过 stdin 读取。

**操作**：与 B2 相同（反序列化 → 过滤 → 排序 → 序列化）。

**输出**：结果 JSON 字符串，写入 stdout。正确性验证：语义级 JSON 比较。

**对应源代码**：

| 工具链 | 算法实现 | WASI 入口 |
|--------|---------|-----------|
| Go / TinyGo | `go/jsonrt/jsonrt.go`（`Process` 函数，与 B2 共享） | `go/cmd/json-wasi/main.go`（stdin/stdout，支持 `--bench N`） |
| Rust | `rust/shared/src/jsonrt.rs`（`process` 函数，与 B2 共享） | `rust/json-wasi/src/main.rs`（stdin/stdout，支持 `--bench N`） |

B2 与 B4 的算法实现代码完全共享，仅入口程序不同：B2 的浏览器入口通过 `syscall/js`（Go）或 `wasm_bindgen`（Rust）与 JavaScript 交互；B4 的 WASI 入口通过 stdin/stdout 进行 I/O。这一设计确保了跨场景对比中性能差异仅来源于运行环境，而非代码实现。

#### 3.3.6 测试用例覆盖率分析

根据前文引用的实证研究数据，四个测试用例的场景覆盖率估计如下：

| 场景 | 测试用例 | 覆盖的负载模式 | 估计覆盖率 | 数据来源 |
|------|---------|--------------|-----------|---------|
| 浏览器 | B1 + B2 | 计算密集型 + 数据处理型 | ~40%–50% | Hilbig et al. [7] |
| 微服务 | B3 + B4 | 计算密集型 + 数据处理型 | ~60%–70% | Roadrunner [13], Lumos [12] |

### 3.4 系统总体架构

#### 3.4.1 项目结构

整个实验项目采用 Monorepo 结构，各语言实现和测试工具放置于统一的代码仓库中：

```
go-rust-wasm-bench/
├── go/                        # Go 源代码（Go 标准编译器与 TinyGo 共享同一份源码）
│   ├── conv/                  # B1 算法实现，图像卷积算法包
│   ├── jsonrt/                # B2/B4 算法实现，JSON 往返处理包
│   ├── sha/                   # B3 算法实现，SHA-256 哈希包
│   └── cmd/                   # 各场景入口程序
│       ├── conv-browser/      # B1 浏览器入口，浏览器端图像卷积（syscall/js 暴露 wasmConvolve）
│       ├── conv-wasi/         # B1 WASI 入口，WASI 端图像卷积（stdin 读像素/stdout 写结果，跨场景参考）
│       ├── json-browser/      # B2 浏览器入口，浏览器端 JSON 往返（syscall/js 暴露 wasmJsonRoundtrip）
│       ├── json-wasi/         # B4 WASI 入口，WASI 端 JSON 往返（stdin 读 JSON/stdout 写结果）
│       └── sha-wasi/          # B3 WASI 入口，WASI 端 SHA-256 哈希（stdin 读字节/stdout 写十六进制摘要）
├── rust/                      # Rust Cargo 工作空间
│   ├── shared/                # 共享算法库（所有 crate 通过依赖引用）
│   │   └── src/
│   │       ├── conv.rs        # B1 算法实现，图像卷积（convolve 函数，无外部 crate 依赖）
│   │       ├── jsonrt.rs      # B2/B4 算法实现，JSON 反序列化→过滤→排序→序列化（serde_json）
│   │       └── sha.rs         # B3 算法实现，SHA-256 哈希（sha2 crate）
│   ├── conv-browser/          # B1 浏览器入口，浏览器端图像卷积（#[wasm_bindgen] 导出 convolve）
│   ├── conv-wasi/             # B1 WASI 入口，WASI 端图像卷积（stdin/stdout，跨场景参考）
│   ├── json-browser/          # B2 浏览器入口，浏览器端 JSON 往返（#[wasm_bindgen] 导出 json_roundtrip）
│   ├── json-wasi/             # B4 WASI 入口，WASI 端 JSON 往返（stdin/stdout）
│   └── sha-wasi/              # B3 WASI 入口，WASI 端 SHA-256 哈希（stdin/stdout）
├── testdata/                  # B1–B4 共享测试数据及预计算参考输出
│   └── generate.go            # 确定性数据生成器（固定种子 42）
├── harness/                   # 测试驱动框架
│   ├── browser/               # B1/B2 浏览器测试：HTML 页面 + Playwright 脚本
│   ├── wasi/                  # B3/B4 WASI 测试：hyperfine + 内部计时脚本
│   └── build-time.sh          # 构建时间（C2）测量脚本
├── build/                     # 编译产物（15 个 .wasm 文件）
├── results/                   # 实验结果数据（JSON 格式）
├── Makefile                   # 统一构建与测试自动化入口
├── package.json               # Node.js 依赖（Playwright）
├── go.mod                     # Go 模块定义
├── BENCHMARK.md               # 基准测试方案（英文）
├── BENCHMARK_zhCN.md          # 基准测试方案（中文）
└── DRAFT.md                   # 论文初稿
```

Go 和 TinyGo **共享完全相同的源代码**（`go/conv/`、`go/jsonrt/`、`go/sha/` 及 `go/cmd/` 下的各入口程序），仅通过不同的编译命令（`go build` vs `tinygo build`）生成不同的 `.wasm` 产物。这一设计确保了语言层面的公平性——性能差异完全来自编译器后端，而非代码实现的不同。

Rust 使用 Cargo 工作空间（workspace）组织，共享算法库位于 `rust/shared/`，各场景的 crate 通过 `shared` 依赖引用共享代码。

#### 3.4.2 测试框架设计

浏览器端和 WASI 端的性能测量分别面临不同的技术挑战，本文为两类场景设计了针对性的自动化测试框架。

**(1) 浏览器端：基于 Playwright 的自动化测试**

浏览器端 Wasm 性能测量面临的核心挑战在于**环境一致性**：手动操作浏览器难以精确控制页面加载时机、后台进程干扰以及 JavaScript 引擎的 JIT 状态，人为操作引入的变异将显著降低测量结果的可信度。为解决这一问题，本文采用 Playwright 自动化测试框架驱动浏览器基准测试，主要基于以下考虑：

- **可编程的浏览器控制**：Playwright 提供完整的浏览器生命周期管理 API，支持以无头（headless）模式启动 Chromium，并通过 `page.evaluate()` 在页面上下文中执行 JavaScript 代码。这使得测试脚本可以精确控制 Wasm 模块的加载时机、预热迭代和测量迭代的执行顺序，消除人为操作的不确定性。
- **进程级隔离**：每个（工具链 × 测试用例 × 输入规模）组合在独立的浏览器上下文（`browser.newContext()`）中运行，确保前一组测试的内存状态、JIT 编译缓存不会影响后续测试。
- **一致的启动参数**：通过 Playwright 的 `args` 选项向 Chromium 传递固定的启动参数（`--disable-extensions`、`--disable-background-networking`、`--disable-gpu`、`--js-flags="--no-opt"` 等），排除浏览器扩展、后台网络请求和 GPU 加速等干扰因素。其中 `--js-flags="--no-opt"` 禁用 JavaScript 的 TurboFan 优化编译器，避免 JS 胶水代码的 JIT 优化程度差异影响计时精度——需注意该参数不影响 Wasm 本身的编译，Wasm 模块始终由 V8 的 Liftoff/TurboFan 编译。
- **跨源隔离支持**：测试所用的 HTTP 服务器设置了 `Cross-Origin-Opener-Policy: same-origin` 和 `Cross-Origin-Embedder-Policy: require-corp` 响应头，满足 `performance.measureUserAgentSpecificMemory()` API 的跨源隔离要求，使内存增量测量（R3）成为可能。

浏览器测试页面（`conv.html`、`json.html`）通过 URL 查询参数（`?tc=go|tinygo|rust`）选择工具链，页面内部根据参数动态加载对应的 Wasm 模块——Go/TinyGo 通过 `wasm_exec.js` + `WebAssembly.instantiateStreaming()` 加载，Rust 通过 wasm-bindgen 生成的 ES 模块动态导入加载。加载完成后，页面将模块实例化耗时记录到 `window.__initTimeMs`（R1），并暴露统一的 `window.__run()` 函数供 Playwright 脚本调用。这种设计使得同一页面模板可服务于三条工具链，避免了重复的 HTML 代码。

**(2) WASI 端：hyperfine + 内部计时**

WASI 场景的性能测量需要区分两个层次：**冷启动性能**（包含 Wasmtime 进程启动、模块编译和实例化）和**暖执行性能**（纯计算内核耗时）。本文采用两种互补的工具实现这一区分：

- **冷启动测量（R4）**：使用 hyperfine —— 一款成熟的命令行基准工具。hyperfine 自动执行预热轮次（`--warmup 3`），然后进行统计学上有意义的多次采样（`--runs 30`），计算均值、标准差和离群值检测，并将原始数据导出为 JSON。相比手动编写计时脚本，hyperfine 的统计方法更为严谨，结果可直接用于论文报告。
- **暖执行测量（R5）**：在 Wasm 模块内部实现计时循环，通过 `--bench N` 命令行参数激活。模块在单次进程调用中执行 5 次预热迭代（结果丢弃）和 30 次测量迭代，使用各语言的高精度计时 API（Go: `time.Now()` / Rust: `std::time::Instant`）对每次迭代单独计时，耗时数据输出到 stderr（stdout 保留给计算结果）。内部计时的优势在于完全消除了进程启动和 Wasmtime 模块编译的开销，隔离测试纯算法执行性能。
- **峰值内存测量（R6）**：使用 macOS 系统工具 `/usr/bin/time -l`，报告进程生命周期内的最大常驻集大小（maximum resident set size），反映 Wasm 运行时和模块的总内存占用。

**(3) 迭代策略的统计学依据**

所有运行时指标采用 **5 次预热 + 30 次测量**的迭代策略。5 次预热确保浏览器端的 V8 JIT 编译器完成对 Wasm 代码的优化编译（从 Liftoff 基线编译器到 TurboFan 优化编译器的升级），以及 WASI 端 CPU 缓存和分支预测器达到稳态。30 次测量采样满足中心极限定理对样本量的基本要求（N ≥ 30），使得即使底层分布非正态，样本均值的分布仍近似正态，可用于后续的 Mann-Whitney U 非参数检验。构建时间采用 5 次清洁构建取中位数，因编译过程通常较为稳定，5 次采样已足以捕捉典型值。

#### 3.4.3 数据流设计

浏览器场景数据流：

```
testdata/generate.go  →  testdata/（JSON、RGBA、SHA 输入 + 参考输出）
                              ↓ [HTTP 服务器提供文件]
                   Playwright 脚本（harness/browser/bench.mjs）
                              ↓ [启动 Chromium，导航到测试页]
                   HTML 测试页（conv.html / json.html）
                              ↓ [加载 wasm_exec.js 或 wasm-bindgen JS 胶水]
                   WebAssembly.instantiateStreaming() → 记录 R1
                              ↓ [page.evaluate() 驱动迭代]
                   5 次预热 + 30 次测量（performance.now()）→ 记录 R2
                              ↓ [measureUserAgentSpecificMemory()]
                   内存增量 → 记录 R3
                              ↓
                   results/browser/*.json
```

WASI 场景数据流：

```
testdata/generate.go  →  testdata/（JSON、RGBA、SHA 输入 + 参考输出）
                              ↓ [stdin 重定向]
                   hyperfine  →  wasmtime run module.wasm  → 记录 R4（冷启动）
                   wasmtime run module.wasm --bench 35      → 记录 R5（暖执行，
                         stderr 输出每次迭代耗时，stdout 输出计算结果）
                   /usr/bin/time -l wasmtime run module.wasm → 记录 R6（峰值内存）
                              ↓
                   results/wasi/*.json
```

#### 3.4.4 正确性保障

在任何性能测量之前，必须验证所有实现产生相同的输出：

1. 使用独立的测试数据生成器（`testdata/generate.go`）确定性地生成所有输入数据和参考输出，确保所有工具链使用完全相同的测试数据。
2. 对每个（工具链 × 测试用例 × 输入规模）组合，将 Wasm 输出与参考值对比。
3. 对比规则：图像卷积允许逐像素 ±1 容差（因浮点取整）；JSON 处理采用**语义级比较**（分别解析两份 JSON 并比较数据结构是否相等），因 Go 的 `encoding/json` 与 Rust 的 `serde_json` 对浮点数的序列化格式存在差异（如 `95.0` 在 Go 中可能序列化为 `95`，在 Rust 中保留为 `95.0`）；SHA-256 要求十六进制摘要精确匹配。
4. 任何不匹配均为阻断性错误，必须先修复再进行性能测量。

#### 3.4.5 统计分析方法

对每项指标报告均值、中位数、标准差、最小值和最大值。运行时指标采集 30 个样本（N = 30），构建时间采集 5 个样本（N = 5）。

采用 Mann-Whitney U 检验（非参数检验，不假设正态分布）判断工具链之间的性能差异是否具有统计显著性，显著性水平设为 α = 0.05。对三对比较（Go vs Rust、TinyGo vs Rust、Go vs TinyGo）分别报告 p 值。

可视化方案包括：箱线图（展示执行时间分布）、柱状图（展示二进制体积和构建时间）、折线图（展示性能随输入规模的变化趋势）。

### 3.5 本章小结

本章完成了实验环境的规划与系统总体设计。实验在同一台 Apple M3 Max 物理机上运行，使用统一版本的编译器（Go 1.25.8 / TinyGo 0.40.1 / Rust 1.94.0）和运行时（Wasmtime 33.0.0）；评价指标体系涵盖编译特性、运行性能和工程效率三个维度共 9 项定量指标和 1 项定性指标；四个测试用例基于实证研究选取，覆盖计算密集型和数据处理型两大负载模式；项目采用 Monorepo 结构确保测试数据共享和实验流程一致。Go 和 TinyGo 共享完全相同的源代码，Rust 使用 Cargo 工作空间组织共享算法库，构建过程通过 Makefile 统一管理（`make all` 一键编译 15 个 Wasm 二进制，`make verify` 一键验证正确性）。后续两章将分别介绍 Go 和 Rust 的 WebAssembly 实现过程。

---

## 第 4 章 基于 Go 的 WebAssembly 应用实现

本章详细介绍使用 Go 标准编译器和 TinyGo 将基准测试程序编译为 WebAssembly 模块的实现过程。Go 和 TinyGo 共享完全相同的源代码，仅通过编译命令的差异生成不同的 `.wasm` 产物。

### 4.1 Go 模块组织

项目使用 Go Modules 管理依赖，`go.mod` 文件定义如下：

```
module github.com/universonic/go-rust-wasm-bench

go 1.25
```

由于所有算法实现仅依赖 Go 标准库（`crypto/sha256`、`encoding/json`、`math`、`sort`），项目无第三方依赖，这也意味着 TinyGo 可以在无兼容性障碍的情况下编译相同的源代码。

算法代码组织为三个内部包：

- `go/conv/`：图像卷积算法，导出 `Convolve` 函数和 `KernelBySize` 辅助函数。
- `go/jsonrt/`：JSON 往返处理，导出 `Process` 函数，定义 `User` 结构体。
- `go/sha/`：SHA-256 哈希，导出 `Sum256Hex` 函数。

### 4.2 算法实现

#### 4.2.1 图像卷积（conv 包）

`Convolve` 函数接收 RGBA 像素切片、图像宽高和卷积核矩阵，对 R、G、B 三通道分别执行二维卷积，Alpha 通道直接复制。实现要点包括：

- **边界处理**：采用零填充策略，超出图像边界的像素值视为 0。
- **归一化**：在卷积前计算核元素之和 `kSum`，每个输出像素值除以 `kSum` 以保持亮度不变。
- **数值精度**：中间计算使用 `float64` 类型，最终通过 `math.Round` 四舍五入并钳位至 [0, 255] 范围内，转换为 `byte` 类型。
- **卷积核定义**：`Kernel3` 和 `Kernel5` 作为包级变量预定义，`KernelBySize` 函数根据尺寸参数返回对应的核矩阵。

#### 4.2.2 JSON 往返处理（jsonrt 包）

`Process` 函数接收 JSON 字节切片，执行反序列化→过滤→排序→序列化的完整流程：

1. 使用 `encoding/json.Unmarshal` 将 JSON 反序列化为 `[]User` 切片。
2. 遍历过滤 `Age >= 18` 的记录。
3. 使用 `sort.Slice` 按 `Score` 降序排列，`Score` 相同时按 `ID` 升序排列。
4. 使用 `json.Marshal` 将结果序列化回 JSON 字节切片。

`User` 结构体使用 JSON 标签（`json:"id"` 等）控制序列化字段名。`encoding/json` 对浮点数的序列化行为是：整数值的浮点数省略小数点（如 `95.0` 序列化为 `95`），这与 Rust 的 `serde_json`（始终保留 `.0`）存在差异，是后续正确性验证采用语义比较的直接原因。

#### 4.2.3 SHA-256 哈希（sha 包）

`Sum256Hex` 函数调用标准库 `crypto/sha256.Sum256` 计算摘要，再使用 `fmt.Sprintf("%x", h)` 将 32 字节摘要转换为 64 字符的小写十六进制字符串。实现简洁——标准库已提供完整的 SHA-256 实现，无需引入第三方库。

### 4.3 浏览器端入口实现

浏览器端 Wasm 模块通过 `GOOS=js GOARCH=wasm` 编译，使用 `syscall/js` 包 [8] 与 JavaScript 环境交互。

#### 4.3.1 卷积浏览器入口

`go/cmd/conv-browser/main.go` 的实现逻辑如下：

1. 在 `main` 函数中，通过 `js.Global().Set("wasmConvolve", js.FuncOf(convolve))` 将 Go 函数注册为 JavaScript 全局函数。
2. 使用 `select {}` 阻塞主 goroutine，保持 Wasm 实例存活。
3. `convolve` 回调函数从 JavaScript 参数中提取 `Uint8Array`（图像数据）、宽度、高度和卷积核大小，使用 `js.CopyBytesToGo` 将像素数据从 JavaScript 内存复制到 Go 的线性内存中。
4. 调用 `conv.Convolve` 执行卷积计算。
5. 使用 `js.CopyBytesToJS` 将结果复制回一个新建的 `Uint8Array` 并返回。

`js.CopyBytesToGo` / `js.CopyBytesToJS` 是 Go 标准库提供的批量数据传输 API，通过一次调用完成整块内存的复制，避免了逐字节操作的性能损失。

#### 4.3.2 JSON 浏览器入口

`go/cmd/json-browser/main.go` 将 `wasmJsonRoundtrip` 注册为全局函数。与卷积入口不同，JSON 数据以字符串形式传递——通过 `args[0].String()` 获取输入 JSON 字符串，调用 `jsonrt.Process` 处理后，将结果以 `js.ValueOf(string(result))` 返回。字符串类型可由 `syscall/js` 运行时直接在 JavaScript 和 Go 之间传递，无需额外的内存复制操作。

### 4.4 WASI 端入口实现

WASI 端 Wasm 模块通过 `GOOS=wasip1 GOARCH=wasm` 编译 [18]，使用标准的文件 I/O 和命令行参数接口。

三个 WASI 入口程序（`conv-wasi`、`json-wasi`、`sha-wasi`）遵循统一的设计模式：

1. **参数解析**：通过 `os.Args` 获取命令行参数。卷积入口需要 `width height kernel_size` 三个位置参数；SHA-256 和 JSON 入口无位置参数。所有入口均支持可选的 `--bench N` 参数。
2. **数据读取**：通过 `io.ReadAll(os.Stdin)` 从标准输入读取全部输入数据。
3. **计时循环**：当 `--bench N` 参数存在且 N > 1 时，程序进入基准模式：前 5 次为预热迭代（不计时），后 N−5 次为测量迭代。每次测量迭代使用 `time.Now()` 和 `time.Since(start)` 计时，将耗时以 `iteration i: x.xxxxxx ms` 格式输出到 stderr。
4. **结果输出**：最终计算结果写入 stdout。

这种 stdout/stderr 分离设计确保了计算结果和计时数据不会混合，便于测试框架分别采集。

### 4.5 Go 标准编译器与 TinyGo 编译流程

#### 4.5.1 Go 标准编译器

Go 标准编译器编译 Wasm 的命令格式为：

```bash
# 浏览器目标
GOOS=js GOARCH=wasm go build -ldflags="-s -w" -o output.wasm ./go/cmd/xxx

# WASI 目标
GOOS=wasip1 GOARCH=wasm go build -ldflags="-s -w" -o output.wasm ./go/cmd/xxx
```

Go 标准编译器使用 `gc` 后端（非 LLVM），编译产物包含完整的 Go 运行时：goroutine 调度器、垃圾回收器（GC）、栈管理、内存分配器等。这使得即使是功能简单的程序，其 Wasm 二进制文件也通常在数 MB 级别。Go 编译器可通过 `-ldflags="-s -w"` 去除符号表（`-s`）和 DWARF 调试信息（`-w`）以减小产物体积，但因完整运行时的存在，优化幅度有限。

浏览器端运行需要配合 `wasm_exec.js` 胶水文件（位于 `$(go env GOROOT)/lib/wasm/wasm_exec.js`），该文件由 Go 官方维护，提供了 `fs`、`process`、`crypto` 等 Node.js/浏览器 API 的 polyfill 以及 Go 运行时与 JavaScript 之间的桥接逻辑。

#### 4.5.2 TinyGo 编译器

TinyGo 的编译命令格式为：

```bash
# 浏览器目标
tinygo build -target=wasm -opt=z -no-debug -o output.wasm ./go/cmd/xxx

# WASI 目标
tinygo build -target=wasip1 -opt=z -no-debug -o output.wasm ./go/cmd/xxx
```

TinyGo 基于 LLVM 后端 [9]，通过以下机制减小产物体积：

- **死代码消除**：LLVM 的链接时优化（LTO）移除未引用的函数和数据。
- **精简运行时**：TinyGo 使用自己的轻量级运行时替代标准 Go 运行时，GC 采用保守式标记-清除算法，调度器更为简单。
- **优化标志**：`-opt=z` 指示 LLVM 以最小代码体积为目标进行优化（等价于 Clang/LLVM 的 `-Oz`）；`-no-debug` 去除 DWARF 调试符号。

TinyGo 浏览器端使用自己维护的 `wasm_exec.js`（位于 `$(tinygo env TINYGOROOT)/targets/wasm_exec.js`），与 Go 标准版本不兼容，两者的 `Go` 构造函数和 `importObject` 结构不同。项目中通过 `make copy-wasm-exec` 将两个版本分别复制为 `wasm_exec_go.js` 和 `wasm_exec_tinygo.js`，由 HTML 测试页根据工具链参数动态选择加载。

### 4.6 本章小结

本章介绍了基于 Go 的 WebAssembly 应用实现过程。Go 和 TinyGo 共享完全相同的源代码（三个算法包和五个入口程序），通过不同的编译命令分别生成 10 个 `.wasm` 文件（浏览器 2 个 + WASI 3 个，×2 编译器）。浏览器端通过 `syscall/js` 包实现 JavaScript 互操作，WASI 端通过标准 I/O 接口实现数据传递。两种编译器的核心差异在于后端架构（gc vs LLVM）和运行时规模（完整 vs 精简），这些差异将直接体现在后续的编译产物体积和运行性能实验数据中。

---

## 第 5 章 基于 Rust 的 WebAssembly 应用实现

本章详细介绍使用 Rust 将基准测试程序编译为 WebAssembly 模块的实现过程，包括 Cargo 工作空间配置、算法实现、浏览器与 WASI 入口的构建方式。

### 5.1 Cargo 工作空间组织

Rust 代码采用 Cargo 工作空间（workspace）组织 [23]，根目录 `rust/Cargo.toml` 定义了工作空间结构：

```toml
[workspace]
members = [
    "shared",
    "conv-browser", "conv-wasi",
    "json-browser", "json-wasi",
    "sha-wasi",
]
resolver = "2"

[workspace.dependencies]
shared = { path = "shared" }
wasm-bindgen = "0.2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
sha2 = "0.10"

[profile.release]
opt-level = "z"
lto = true
strip = true
codegen-units = 1
panic = "abort"
```

工作空间包含 6 个 crate：1 个共享算法库（`shared`）和 5 个入口 crate。`[workspace.dependencies]` 统一管理依赖版本，确保所有 crate 使用相同版本的第三方库。

`[profile.release]` 中的优化配置是 Rust Wasm 体积优化的关键：

- `opt-level = "z"`：指示 LLVM 以最小代码体积为优化目标，与 TinyGo 的 `-opt=z` 等价。
- `lto = true`：启用链接时优化，跨 crate 边界消除死代码。
- `strip = true`：去除符号表和调试信息。
- `codegen-units = 1`：将整个 crate 作为单个编译单元处理，给予 LLVM 更大的优化空间，代价是编译速度变慢。
- `panic = "abort"`：将 panic 处理策略从默认的栈展开（unwinding）改为立即中止（abort），省去展开表和析构逻辑的代码生成，进一步减小产物体积。

### 5.2 共享算法库（shared crate）

`rust/shared/` 作为纯 Rust 库，导出三个模块：

```rust
pub mod conv;
pub mod jsonrt;
pub mod sha;
```

#### 5.2.1 图像卷积（conv 模块）

`convolve` 函数的签名为 `fn convolve(img: &[u8], w: usize, h: usize, kernel: &[&[f64]]) -> Vec<u8>`，实现逻辑与 Go 版本完全对齐：

- 使用 `f64` 浮点类型进行中间计算。
- 通过迭代器链 `kernel.iter().flat_map(|row| row.iter()).sum()` 计算核元素之和。
- 边界检查使用 `isize` 类型转换避免无符号整数下溢。
- 输出值通过 `.round().clamp(0.0, 255.0)` 实现四舍五入和钳位。

该模块无外部 crate 依赖，仅使用 Rust 标准库的 `Vec` 和基本数值运算。

#### 5.2.2 JSON 往返处理（jsonrt 模块）

`process` 函数签名为 `fn process(input: &[u8]) -> Result<Vec<u8>, String>`，依赖 `serde` [24] 和 `serde_json` [25] 两个 crate：

1. `serde_json::from_slice::<Vec<User>>(input)` 零拷贝反序列化 JSON。
2. `users.into_iter().filter(|u| u.age >= 18).collect()` 函数式过滤。
3. `filtered.sort_by(|a, b| ...)` 按 `score` 降序、`id` 升序排列，使用 `partial_cmp` 处理浮点比较并以 `then_with` 链接次级排序。
4. `serde_json::to_vec(&filtered)` 序列化为 JSON 字节向量。

`User` 结构体通过 `#[derive(Serialize, Deserialize)]` 属性宏自动生成序列化/反序列化代码，`serde` 的 proc-macro 在编译时展开，运行时零开销。

`serde_json` 对浮点数的序列化行为与 Go 不同：`95.0` 在 Rust 中序列化为 `95.0`（保留小数点），而 Go 的 `encoding/json` 序列化为 `95`。两种行为均符合 JSON 规范（RFC 8259 [26]），这也是正确性验证采用语义级比较的原因。

#### 5.2.3 SHA-256 哈希（sha 模块）

`sum256_hex` 函数使用 `sha2` crate [27] 的 `Sha256` 类型：

```rust
let mut hasher = Sha256::new();
hasher.update(data);
let result = hasher.finalize();
```

摘要结果通过自定义的 `hex_encode` 函数转换为十六进制字符串。选择 `sha2` crate 而非其他实现的原因是：`sha2` 是 RustCrypto 项目 [28] 维护的标准 SHA-2 实现，是 Rust 生态中使用最广泛的 SHA-256 库，且在 Wasm 环境中自动回退到纯软件实现（不依赖 CPU 硬件指令），保证了与 Go 标准库 `crypto/sha256` 在公平性上的一致。

### 5.3 浏览器端入口实现

浏览器端 crate（`conv-browser`、`json-browser`）编译为 `cdylib` 类型，使用 `wasm-bindgen` [10] 实现 JavaScript 互操作。

#### 5.3.1 crate 类型与 wasm-bindgen

`Cargo.toml` 中的 `[lib] crate-type = ["cdylib"]` 指示 Rust 编译器生成动态库格式的 Wasm 模块，该格式适合作为 JavaScript 模块导入。编译后需通过 `wasm-bindgen` CLI 工具进行后处理：

```bash
cargo build --release --target wasm32-unknown-unknown -p conv-browser -p json-browser
wasm-bindgen --target web --out-dir build/rust-conv-browser \
    rust/target/wasm32-unknown-unknown/release/conv_browser.wasm
```

`wasm-bindgen --target web` 生成两个文件：
- `conv_browser_bg.wasm`：经过后处理的 Wasm 二进制（移除了 wasm-bindgen 的自定义段，插入了标准的 JS 互操作粘合指令）。
- `conv_browser.js`：ES 模块格式的 JavaScript 胶水代码，提供 `default()` 初始化函数和类型安全的导出函数。

#### 5.3.2 卷积浏览器入口

`rust/conv-browser/src/lib.rs` 仅需 7 行代码：

```rust
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn convolve(img: &[u8], w: u32, h: u32, kernel_size: u32) -> Vec<u8> {
    let kernel = shared::conv::kernel_by_size(kernel_size as usize);
    shared::conv::convolve(img, w as usize, h as usize, kernel)
}
```

`#[wasm_bindgen]` 属性宏自动生成 `&[u8]` ↔ `Uint8Array` 和 `Vec<u8>` → `Uint8Array` 的转换代码。与 Go 需要手动调用 `js.CopyBytesToGo` / `js.CopyBytesToJS` 不同，Rust 端的类型转换完全由 wasm-bindgen 在编译时自动完成，开发者无需编写显式的内存复制逻辑。

#### 5.3.3 JSON 浏览器入口

`rust/json-browser/src/lib.rs` 同样简洁：

```rust
#[wasm_bindgen]
pub fn json_roundtrip(input: &str) -> String {
    match shared::jsonrt::process(input.as_bytes()) {
        Ok(v) => String::from_utf8(v).unwrap_or_else(|_| "error: invalid utf8".into()),
        Err(e) => format!("error: {e}"),
    }
}
```

wasm-bindgen 自动处理 JavaScript 字符串 ↔ Rust `&str` / `String` 的转换，利用 `TextEncoder` / `TextDecoder` API 在 UTF-16（JavaScript）和 UTF-8（Rust）之间进行编码转换。

### 5.4 WASI 端入口实现

WASI 端 crate（`conv-wasi`、`json-wasi`、`sha-wasi`）编译为标准可执行文件，使用 `wasm32-wasip1` 编译目标：

```bash
cargo build --release --target wasm32-wasip1 -p conv-wasi -p json-wasi -p sha-wasi
```

三个 WASI 入口程序遵循与 Go 版本相同的设计模式（参数解析 → 数据读取 → 计时循环 → 结果输出），但使用 Rust 的标准库 API：

- **参数解析**：`std::env::args().collect::<Vec<String>>()` 获取命令行参数。
- **数据读取**：`io::stdin().read_to_end(&mut data)` 从 stdin 读取全部输入。
- **高精度计时**：`std::time::Instant::now()` 和 `start.elapsed()` 提供纳秒级精度的单调时钟计时。在 WASI 环境中，`Instant` 通过 WASI 的 `clock_time_get` 系统调用获取时间，不受系统时钟调整的影响。
- **输出分离**：计时数据通过 `eprintln!` 输出到 stderr，计算结果通过 `io::stdout().write_all` 输出到 stdout。

与 Go 版本的一个显著差异是：Rust 使用 `let (warmup, measured) = if iterations > 1 { (5, iterations - 5) } else { (0, 1) };` 模式匹配一次性确定预热和测量次数，而 Go 使用 `if-else` 赋值。两种写法功能等价，但体现了两种语言的惯用表达差异。

### 5.5 Rust 与 Go 的 Wasm 编译差异

| 方面 | Go 标准编译器 | TinyGo | Rust |
|------|-------------|--------|------|
| 编译后端 | gc（Go 自有） | LLVM | LLVM |
| 运行时 | 完整（GC + 调度器） | 精简（保守式 GC） | 无（零成本抽象） |
| 浏览器 JS 互操作 | `syscall/js` + `wasm_exec.js` | `syscall/js` + TinyGo `wasm_exec.js` | wasm-bindgen + 生成的 ES 模块 |
| 浏览器编译目标 | `GOOS=js GOARCH=wasm` | `-target=wasm` | `wasm32-unknown-unknown` |
| WASI 编译目标 | `GOOS=wasip1 GOARCH=wasm` | `-target=wasip1` | `wasm32-wasip1` |
| 体积优化手段 | `-ldflags="-s -w"` | `-opt=z -no-debug` | `opt-level="z"`, LTO, strip, `panic="abort"` |
| 第三方依赖 | 无（纯标准库） | 无（纯标准库） | serde, serde_json, sha2, wasm-bindgen |

### 5.6 本章小结

本章介绍了基于 Rust 的 WebAssembly 应用实现过程。Rust 通过 Cargo 工作空间组织 6 个 crate，共享算法库 `shared` 提供核心算法实现。浏览器端使用 wasm-bindgen 实现类型安全的 JavaScript 互操作，WASI 端使用标准 I/O 接口。与 Go 相比，Rust 的实现具有以下特点：(1) 无运行时开销——没有 GC 和调度器嵌入产物；(2) 需要第三方 crate 支持（serde、sha2），但这些 crate 是 Rust 生态的事实标准；(3) wasm-bindgen 提供了更自动化的 JavaScript 类型转换，减少了手动内存管理的模板代码。这些差异将在下一章的实验数据中得到量化体现。

---

## 第 6 章 实验测试与性能对比分析

本章在前述实验环境和系统设计的基础上，执行基准测试并对实验数据进行分析。实验按照第 3 章定义的测试流程，依次采集编译指标、运行性能指标和工程效率指标，并使用统计方法对三条工具链（Go 标准编译器、TinyGo、Rust）的表现进行对比。

> **实验环境**：Apple M3 Max, macOS, Wasmtime 33.0.0, Chromium 145.0.7632.6（完整通道，启用 `--enable-experimental-web-platform-features` 以获取内存测量 API）。每项基准测试执行 5 次预热 + 30 次正式测量，取中位数/均值。

### 6.1 正确性验证

在进行任何性能测量之前，首先通过 `make verify` 验证所有实现的正确性。验证结果应如下：

```
=== SHA-256 ===
  sha-wasi-go: PASS
  sha-wasi-tinygo: PASS
  sha-wasi-rust: PASS
=== JSON (WASI, semantic) ===
  json-wasi-go: PASS
  json-wasi-tinygo: PASS
  json-wasi-rust: PASS
=== Convolution 256x256 K3 ===
  conv-wasi-go: PASS
  conv-wasi-tinygo: PASS
  conv-wasi-rust: PASS
=== Convolution 256x256 K5 ===
  conv-wasi-go: PASS
  conv-wasi-tinygo: PASS
  conv-wasi-rust: PASS
```

所有 12 项验证（3 工具链 × 4 验证用例）均需通过，确认三条工具链在功能层面产生等价的输出。

### 6.2 编译指标分析

#### 6.2.1 二进制体积（C1）

| 产物文件 | Go (bytes) | TinyGo (bytes) | Rust (bytes) |
|----------|-----------|----------------|-------------|
| conv-browser | 1,759,473 | 43,712 | 12,050 |
| json-browser | 3,155,688 | 418,900 | 74,542 |
| conv-wasi | 2,499,237 | 198,780 | 82,335 |
| json-wasi | 3,173,085 | 479,069 | 133,237 |
| sha-wasi | 2,672,573 | 284,314 | 86,495 |

分析维度：

1. **绝对体积对比**：Go 标准编译器的 Wasm 产物最大（1.8–3.2 MB），即便使用 `-ldflags="-s -w"` 去除符号表和调试信息后仍然较大，因其嵌入了完整的 Go 运行时（GC、goroutine 调度器等）。TinyGo 通过 LLVM 死代码消除和精简运行时将体积降低至 44–479 KB。Rust 由于无 GC 运行时开销，加之 LTO、`opt-level = "z"` 和 `panic = "abort"` 优化，产物最小（12–133 KB），与 Go 相比可减小 24–146 倍。
2. **浏览器 vs WASI 差异**：同一工具链下，浏览器目标和 WASI 目标的产物体积可能存在差异，原因在于两种目标链接的系统库和胶水代码不同。
3. **功能复杂度影响**：对比仅使用标准库的模块（conv、sha）与使用序列化框架的模块（json），观察第三方依赖对产物体积的影响。

![图 6-1：二进制体积对比柱状图](results/figures/fig_6_1_binary_size.png)

*图 6-1：二进制体积对比柱状图。横轴为 5 个产物文件，纵轴为文件大小（KB），三条工具链分组柱状对比。*

#### 6.2.2 构建时间（C2）

| 构建目标 | Go 中位数 (s) | TinyGo 中位数 (s) | Rust 中位数 (s) |
|----------|-------------|-------------------|----------------|
| conv-browser | 1.0694 | 0.6475 | （合并统计） |
| json-browser | 1.5341 | 2.1965 | （合并统计） |
| conv-wasi | 1.4347 | 1.5301 | （合并统计） |
| json-wasi | 1.5637 | 2.4006 | （合并统计） |
| sha-wasi | 1.4986 | 2.1827 | （合并统计） |
| 浏览器目标合计 | 2.6035 | 2.8440 | 2.8329 |
| WASI 目标合计 | 4.4970 | 6.1134 | 2.7338 |

> 注：Rust 的浏览器目标和 WASI 目标分别作为一个整体编译（`cargo build` 同时编译多个 crate），因此 Rust 按目标类型合并统计。

分析维度：

1. **首次清洁构建时间**：5 次清洁构建的中位数。Go 标准编译器的单模块编译速度较快（~1.1–1.6 s），但由于逐个编译，多目标合计时间并不占优。TinyGo 在简单模块（conv-browser 0.65 s）上甚至快于 Go，但含第三方依赖的模块（json-browser 2.20 s）较慢。Rust 通过 Cargo 并行编译多个 crate，WASI 合计（2.73 s）反而低于 Go 合计（4.50 s）。
2. **Rust 的 LTO 开销**：`lto = true` 和 `codegen-units = 1` 虽然有助于减小产物体积和提升运行性能，但会显著增加编译时间。
3. **体积-时间权衡**：结合 C1 和 C2 分析各工具链在"编译时间换产物体积"上的效率。

![图 6-2：构建时间对比柱状图](results/figures/fig_6_2_build_time.png)

*图 6-2：构建时间对比柱状图。横轴为构建目标，纵轴为中位构建时间（秒），三条工具链分组对比。*

![图 6-3：编译效率散点图](results/figures/fig_6_3_compile_efficiency.png)

*图 6-3：编译效率散点图。横轴为构建时间（秒），纵轴为二进制体积（KB），每个点代表一个（工具链 × 目标）组合，揭示"编译时间换体积"的权衡关系。*

### 6.3 浏览器端性能分析

#### 6.3.1 B1：图像卷积

**模块实例化时间（R1）**：

| 图像尺寸 | 卷积核 | Go R1 (ms) | TinyGo R1 (ms) | Rust R1 (ms) |
|----------|--------|-----------|----------------|-------------|
| 256×256 | K3 | 20.12 | 11.81 | 10.35 |
| 512×512 | K3 | 21.43 | 11.14 | 10.16 |
| 1024×1024 | K3 | 20.11 | 11.19 | 10.04 |
| 1920×1080 | K3 | 21.16 | 11.26 | 10.38 |
| 256×256 | K5 | 20.94 | 11.14 | 10.39 |
| 512×512 | K5 | 21.71 | 11.18 | 10.38 |
| 1024×1024 | K5 | 21.72 | 10.87 | 10.10 |
| 1920×1080 | K5 | 22.06 | 10.92 | 10.44 |

模块实例化时间主要受二进制体积影响——更大的模块需要更长的编译和实例化时间。R1 与 C1 的相关性分析将揭示体积优化对启动性能的直接效益。

![图 6-4：B1 模块实例化时间对比柱状图](results/figures/fig_6_4_b1_init.png)

*图 6-4：B1 模块实例化时间（R1）对比柱状图。横轴为工具链，纵轴为实例化时间（ms）。*

**执行时间（R2）**：

| 图像尺寸 | 卷积核 | Go 均值 (ms) | TinyGo 均值 (ms) | Rust 均值 (ms) | p 值 (Go vs Rust) |
|----------|--------|-------------|-----------------|---------------|------------------|
| 256×256 | K3 | 10.207 | 3.354 | 3.579 | < 0.001 *** |
| 512×512 | K3 | 41.181 | 13.090 | 13.920 | < 0.001 *** |
| 1024×1024 | K3 | 163.671 | 51.063 | 56.515 | < 0.001 *** |
| 1920×1080 | K3 | 323.534 | 103.370 | 112.048 | < 0.001 *** |
| 256×256 | K5 | 21.296 | 7.101 | 7.740 | < 0.001 *** |
| 512×512 | K5 | 84.339 | 28.568 | 31.749 | < 0.001 *** |
| 1024×1024 | K5 | 338.764 | 113.682 | 127.819 | < 0.001 *** |
| 1920×1080 | K5 | 683.059 | 225.192 | 253.597 | < 0.001 *** |

分析维度：

1. **计算密集度影响**：K5（25 次乘加/像素）vs K3（9 次乘加/像素），观察算术密集度提升是否放大工具链间的性能差距。
2. **规模扩展特性**：从 256×256（~66K 像素）到 1920×1080（~2M 像素），工作量增长约 32 倍，各工具链的执行时间是否呈线性增长。
3. **GC 影响**：Go/TinyGo 在处理大图像时可能触发 GC，表现为执行时间的离群值或更高的标准差。

![图 6-5：B1 执行时间箱线图](results/figures/fig_6_5_b1_boxplot.png)

*图 6-5：B1 执行时间箱线图。左右两组分别为 K3 和 K5，每组包含三条工具链的箱线图，展示 30 次测量的分布特征（中位数、四分位距、离群值）。以 1920×1080 为例。*

![图 6-6：B1 执行时间随图像尺寸变化的折线图](results/figures/fig_6_6_b1_line.png)

*图 6-6：B1 执行时间随图像尺寸变化的折线图。横轴为像素总数（对数刻度），纵轴为平均执行时间（ms），分 K3/K5 两组，每组三条线（Go、TinyGo、Rust）。*

**内存增量（R3）**：

| 图像尺寸 | 卷积核 | Go (bytes) | TinyGo (bytes) | Rust (bytes) |
|----------|--------|-----------|----------------|-------------|
| 256×256 | K3 | 7,613,984 | 20,949,432 | 1,392,408 |
| 512×512 | K3 | 11,270,920 | 84,392,572 | 5,062,100 |
| 1024×1024 | K3 | 18,206,113 | 332,498,385 | 19,698,666 |
| 1920×1080 | K3 | 25,100,117 | 647,466,033 | 16,628,174 |
| 256×256 | K5 | 7,597,304 | 23,050,676 | 1,392,136 |
| 512×512 | K5 | 11,270,856 | 84,392,568 | 5,062,112 |
| 1024×1024 | K5 | 18,206,377 | 332,498,389 | 14,095,758 |
| 1920×1080 | K5 | 25,100,245 | 647,465,753 | 16,628,774 |

![图 6-7：B1 内存增量对比柱状图](results/figures/fig_6_7_b1_memory.png)

*图 6-7：B1 内存增量（R3）对比柱状图。横轴为图像尺寸，纵轴为内存增量（KB），三条工具链分组对比。*

#### 6.3.2 B2：JSON 往返处理

**模块实例化时间（R1）**：

| 记录数 N | Go R1 (ms) | TinyGo R1 (ms) | Rust R1 (ms) |
|----------|-----------|----------------|-------------|
| 100 | 24.67 | 12.13 | 10.51 |

> 注：R1 与输入规模无关（模块实例化发生在数据加载之前），此处仅取一个规模的测量值。

**执行时间（R2）**：

| 记录数 N | Go 均值 (ms) | Go 标准差 | TinyGo 均值 (ms) | TinyGo 标准差 | Rust 均值 (ms) | Rust 标准差 | p 值 (Go vs Rust) |
|----------|-------------|----------|-----------------|--------------|---------------|------------|------------------|
| 100 | 0.717 | 0.130 | 1.008 | 0.996 | 0.225 | 0.065 | < 0.001 *** |
| 1,000 | 4.381 | 0.248 | 4.409 | 1.355 | 0.942 | 0.179 | < 0.001 *** |
| 10,000 | 51.358 | 0.165 | 45.869 | 8.000 | 6.188 | 0.095 | < 0.001 *** |

分析维度：

1. **序列化库性能**：Go `encoding/json` 基于运行时反射，而 Rust `serde` 基于编译时代码生成，两种方案的性能特性差异。
2. **内存分配模式**：JSON 处理涉及大量中间对象的分配和释放，GC（Go/TinyGo）与所有权系统（Rust）在此场景下的表现差异。
3. **JS-Wasm 边界开销**：JSON 字符串的跨边界传递成本，与 B4（WASI stdin/stdout）的对比将揭示该开销的量级。

![图 6-8：B2 执行时间随记录数变化的折线图](results/figures/fig_6_8_b2_line.png)

*图 6-8：B2 执行时间随记录数变化的折线图。横轴为记录数 N（对数刻度），纵轴为平均执行时间（ms），三条线分别代表 Go、TinyGo、Rust。*

![图 6-9：B2 执行时间箱线图](results/figures/fig_6_9_b2_boxplot.png)

*图 6-9：B2 执行时间箱线图（N=10000）。展示三条工具链在最大规模下 30 次测量的分布特征。*

**内存增量（R3）**：

| 记录数 N | Go (bytes) | TinyGo (bytes) | Rust (bytes) |
|----------|-----------|----------------|-------------|
| 100 | 96,526 | 4,024,430 | 131,196 |
| 1,000 | 4,557,407 | 16,856,759 | 701,036 |
| 10,000 | 19,658,872 | 69,699,972 | 6,342,372 |

![图 6-10：B2 内存增量对比柱状图](results/figures/fig_6_10_b2_memory.png)

*图 6-10：B2 内存增量（R3）对比柱状图。横轴为记录数，纵轴为内存增量（KB）。*

### 6.4 WASI 端性能分析

#### 6.4.1 B3：SHA-256 哈希

**冷启动时间（R4）**：

| 输入大小 | Go 均值 (ms) | TinyGo 均值 (ms) | Rust 均值 (ms) |
|----------|-------------|-----------------|---------------|
| 1 KB | 20.9 ± 0.9 | 9.4 ± 1.4 | 8.2 ± 1.2 |
| 64 KB | 22.7 ± 0.6 | 7.8 ± 0.2 | 6.4 ± 0.3 |
| 1 MB | 49.5 ± 1.8 | 19.2 ± 0.2 | 15.9 ± 0.3 |
| 16 MB | 455.1 ± 4.6 | 202.0 ± 1.3 | 167.1 ± 1.4 |

冷启动时间包含 Wasmtime 进程启动、Wasm 模块编译（Cranelift JIT）和实例化，与 C1（二进制体积）存在强相关——更大的模块需要 Cranelift 编译更多的字节码。

![图 6-11：B3 冷启动时间对比柱状图](results/figures/fig_6_11_b3_cold.png)

*图 6-11：B3 冷启动时间（R4）对比柱状图。横轴为输入大小，纵轴为平均冷启动时间（ms），三条工具链分组对比。*

**暖执行时间（R5）**：

| 输入大小 | Go 均值 (ms) | Go 标准差 | TinyGo 均值 (ms) | TinyGo 标准差 | Rust 均值 (ms) | Rust 标准差 | p 值 (Go vs Rust) |
|----------|-------------|----------|-----------------|--------------|---------------|------------|------------------|
| 1 KB | 0.0301 | 0.0022 | 0.0099 | 0.0012 | 0.0075 | 0.0031 | < 0.001 *** |
| 64 KB | 1.3379 | 0.0155 | 0.2748 | 0.0209 | 0.2692 | 0.0078 | < 0.001 *** |
| 1 MB | 21.3176 | 0.0901 | 4.1099 | 0.0559 | 4.2479 | 0.0330 | < 0.001 *** |
| 16 MB | 342.6223 | 6.4258 | 65.4936 | 0.3686 | 67.8299 | 0.3122 | < 0.001 *** |

SHA-256 为纯整数运算（32 位加法、循环移位、逻辑运算），不涉及内存分配，是隔离测试编译器代码生成质量的理想用例。暖执行时间的差异主要来源于：(1) 编译器的指令选择和寄存器分配策略；(2) Wasm 运行时对循环密集型代码的优化效果。

![图 6-12：B3 暖执行时间随输入大小变化的折线图](results/figures/fig_6_12_b3_warm_line.png)

*图 6-12：B3 暖执行时间随输入大小变化的折线图。横轴为输入大小（对数刻度），纵轴为平均执行时间（ms），三条线分别代表 Go、TinyGo、Rust。*

![图 6-13：B3 冷启动与暖执行时间对比双柱图](results/figures/fig_6_13_b3_cold_warm.png)

*图 6-13：B3 冷启动与暖执行时间对比双柱图（以 1 MB 为例）。每组包含冷启动（R4）和暖执行（R5）两根柱，展示进程启动开销与纯计算耗时的比例关系。*

**峰值内存（R6）**：

| 输入大小 | Go (bytes) | TinyGo (bytes) | Rust (bytes) |
|----------|-----------|----------------|-------------|
| 1 KB | 45,187,072 | 18,300,928 | 15,056,896 |
| 64 KB | 45,563,904 | 18,579,456 | 15,319,040 |
| 1 MB | 49,463,296 | 22,659,072 | 18,235,392 |
| 16 MB | 96,108,544 | 87,228,416 | 65,404,928 |

峰值内存反映 Wasmtime 运行时 + Wasm 模块的总内存占用。数据显示 Go 的峰值 RSS 最高（45–96 MB），其嵌入式运行时（包括 GC 堆预分配）带来了显著的基准内存开销；Rust 最低（15–65 MB），TinyGo 居中（18–88 MB）。

![图 6-14：B3 峰值内存对比柱状图](results/figures/fig_6_14_b3_memory.png)

*图 6-14：B3 峰值内存（R6）对比柱状图。横轴为输入大小，纵轴为峰值 RSS（MB），三条工具链分组对比。*

#### 6.4.2 B4：JSON 往返处理

**冷启动时间（R4）**：

| 记录数 N | Go 均值 (ms) | TinyGo 均值 (ms) | Rust 均值 (ms) |
|----------|-------------|-----------------|---------------|
| 100 | 26.4 ± 0.6 | 9.6 ± 0.4 | 6.3 ± 0.2 |
| 1,000 | 46.7 ± 0.5 | 18.1 ± 0.4 | 7.6 ± 0.3 |
| 10,000 | 336.2 ± 8.3 | 100.3 ± 0.5 | 20.6 ± 0.3 |

![图 6-15：B4 冷启动时间对比柱状图](results/figures/fig_6_15_b4_cold.png)

*图 6-15：B4 冷启动时间（R4）对比柱状图。横轴为记录数，纵轴为平均冷启动时间（ms）。*

**暖执行时间（R5）**：

| 记录数 N | Go 均值 (ms) | Go 标准差 | TinyGo 均值 (ms) | TinyGo 标准差 | Rust 均值 (ms) | Rust 标准差 | p 值 (Go vs Rust) |
|----------|-------------|----------|-----------------|--------------|---------------|------------|------------------|
| 100 | 2.1341 | 0.0302 | 0.8459 | 0.1750 | 0.0815 | 0.0074 | < 0.001 *** |
| 1,000 | 22.2418 | 1.6036 | 7.4849 | 1.0104 | 0.8731 | 0.0205 | < 0.001 *** |
| 10,000 | 295.0345 | 33.4339 | 77.3153 | 10.2727 | 8.9441 | 0.1006 | < 0.001 *** |

![图 6-16：B4 暖执行时间随记录数变化的折线图](results/figures/fig_6_16_b4_warm_line.png)

*图 6-16：B4 暖执行时间随记录数变化的折线图。横轴为记录数 N（对数刻度），纵轴为平均执行时间（ms），三条线分别代表 Go、TinyGo、Rust。*

**峰值内存（R6）**：

| 记录数 N | Go (bytes) | TinyGo (bytes) | Rust (bytes) |
|----------|-----------|----------------|-------------|
| 100 | 50,036,736 | 21,610,496 | 15,745,024 |
| 1,000 | 51,003,392 | 23,101,440 | 16,187,392 |
| 10,000 | 55,197,696 | 32,751,616 | 19,906,560 |

![图 6-17：B4 峰值内存对比柱状图](results/figures/fig_6_17_b4_memory.png)

*图 6-17：B4 峰值内存（R6）对比柱状图。横轴为记录数，纵轴为峰值 RSS（MB）。*

#### 6.4.3 B2 与 B4 跨场景对比

B2（浏览器）和 B4（WASI）使用完全相同的算法代码和测试数据，仅运行环境不同。通过对比两者的执行时间，可以量化以下因素的影响：

- **JS-Wasm 边界开销**：B2 的数据通过 JavaScript 字符串传递，B4 通过 stdin/stdout 传递。
- **Wasm 引擎差异**：V8（浏览器）vs Cranelift（Wasmtime）的代码生成质量。
- **字符串编码转换**：浏览器端的 UTF-16 ↔ UTF-8 转换开销。

| 记录数 N | B2 Go (ms) | B4 Go (ms) | B2 TinyGo (ms) | B4 TinyGo (ms) | B2 Rust (ms) | B4 Rust (ms) |
|----------|-----------|-----------|---------------|---------------|-------------|-------------|
| 100 | 0.683 | 2.122 | 0.700 | 0.732 | 0.203 | 0.080 |
| 1,000 | 4.293 | 21.599 | 3.843 | 7.183 | 0.885 | 0.872 |
| 10,000 | 51.360 | 309.477 | 39.037 | 71.844 | 6.170 | 8.927 |

> 注：本表采用各组 30 次测量的**中位数**，以减轻 GC 导致的离群值对跨场景对比的干扰。B2 中位数取自浏览器结果 JSON，B4 中位数取自 WASI 暖执行 stderr 输出。与前文 R2/R5 表（报告均值）存在差异，尤其当分布偏斜时（如 TinyGo N=10000 均值 45.9 ms vs 中位数 39.0 ms）差距明显。

![图 6-18：B2 vs B4 执行时间跨场景对比](results/figures/fig_6_18_b2_vs_b4.png)

*图 6-18：B2（浏览器）vs B4（WASI）执行时间跨场景对比分组柱状图。每个记录数下分 3 组（Go、TinyGo、Rust），每组包含 B2 和 B4 两根柱。*

### 6.5 工程效率分析

#### 6.5.1 源代码行数（E1）

使用 `cloc` 工具统计各语言实现的有效代码行数（排除注释和空行）：

| 统计范围 | Go/TinyGo (SLOC) | Rust (SLOC) |
|---------|------------------|-------------|
| 共享算法代码 | 100 | 82 |
| 浏览器入口 | 39 | 14 |
| WASI 入口 | 135 | 89 |
| 合计 | 274 | 185 |

#### 6.5.2 工具链复杂度（E2）

| 评估项 | Go 标准编译器 | TinyGo | Rust |
|--------|-------------|--------|------|
| 构建步骤数 | 1（go build） | 1（tinygo build） | 1–2（WASI 端仅 cargo build；浏览器端需额外 wasm-bindgen 后处理） |
| 配置文件数 | 1（go.mod） | 1（go.mod，共用） | 1（每个 crate 独立 Cargo.toml，workspace 统一管理） |
| 第三方依赖数 | 0 | 0 | 4（serde, serde_json, sha2, wasm-bindgen） |
| 浏览器胶水文件 | 需要（wasm_exec.js） | 需要（TinyGo wasm_exec.js） | 自动生成 |
| 学习曲线 | 低 | 低（Go 知识可复用） | 中-高（所有权、生命周期、宏） |

Go 和 TinyGo 均只需一条编译命令即可生成可用的 Wasm 模块，无需额外的后处理步骤，且零第三方依赖。Rust 在 WASI 端同样只需一步 `cargo build`，但浏览器端需额外执行 `wasm-bindgen` 后处理（共两步）；此外 Rust 依赖 4 个第三方 crate（serde、serde_json、sha2、wasm-bindgen），工具链复杂度整体高于 Go/TinyGo。

然而，Rust 的 wasm-bindgen 在 JavaScript 互操作方面提供了更高的自动化程度——类型转换代码由编译器自动生成，而 Go 需要开发者手动调用 `js.CopyBytesToGo` / `js.CopyBytesToJS` 等 API 管理内存复制。

![图 6-19：源代码行数对比柱状图](results/figures/fig_6_19_sloc.png)

*图 6-19：源代码行数（E1）对比柱状图。横轴为统计范围（共享算法、浏览器入口、WASI 入口、合计），纵轴为 SLOC，Go/TinyGo 与 Rust 双柱对比。*

### 6.6 综合分析

#### 6.6.1 性能雷达图

![图 6-20：三条工具链综合评估雷达图](results/figures/fig_6_20_radar.png)

*图 6-20：三条工具链综合评估雷达图。12 个维度：C1（二进制体积）、C2（构建时间）、R1-B1（卷积初始化时间）、R2-B1（卷积执行时间）、R3-B1（卷积内存增量）、R2-B2（JSON 浏览器执行时间）、R4-B3（SHA-256 冷启动）、R5-B3（SHA-256 暖执行）、R5-B4（JSON WASI 暖执行）、R6-B3（SHA-256 峰值内存）、E1（代码行数）、E2（工具链复杂度，以第三方依赖数量化）。各维度归一化为 0–1 范围，以最优工具链为基准 0、最差为 1，面积越小综合表现越优。新增 R1-B1 可反映 Go 模块初始化开销显著高于其他两条工具链；R4-B3 可反映 Go 冷启动远慢于 TinyGo/Rust 的问题；R5-B4 可反映 WASI 端 JSON 处理差距远大于浏览器端；R6-B3 可反映 Go 在 WASI 端峰值内存最高的特点；R3-B1 可反映 TinyGo 保守式 GC 的高内存代价；E2 可反映 Rust 在 Wasm 场景下对第三方依赖的更高需求。*

表 6-13 列出雷达图各维度归一化前的原始数据，便于读者核验归一化结果及各工具链的绝对性能差异。

*表 6-13：雷达图 12 维度原始数据*

| 维度 | Go | TinyGo | Rust | 最优 |
|------|-----|--------|------|------|
| C1 二进制体积（平均，bytes） | 2,652,011 | 284,955 | 77,732 | Rust |
| C2 构建时间（合计，s） | 7.1005 | 8.9574 | 5.5667 | Rust |
| R1-B1 卷积初始化时间（1920×1080 K3，ms） | 21.155 | 11.260 | 10.380 | Rust |
| R2-B1 卷积执行时间（1920×1080 K3，ms） | 323.534 | 103.370 | 112.048 | TinyGo |
| R3-B1 卷积内存增量（1920×1080 K3，bytes） | 25,100,117 | 647,466,033 | 16,628,174 | Rust |
| R2-B2 JSON 执行时间（N=10000，ms） | 51.358 | 45.869 | 6.188 | Rust |
| R4-B3 SHA-256 冷启动时间（16 MB，ms） | 455.1 | 202.0 | 167.1 | Rust |
| R5-B3 SHA-256 暖执行时间（16 MB，ms） | 342.622 | 65.494 | 67.830 | TinyGo |
| R5-B4 JSON WASI 暖执行时间（N=10000，ms） | 295.035 | 77.315 | 8.944 | Rust |
| R6-B3 SHA-256 峰值内存（16 MB，bytes） | 96,108,544 | 87,228,416 | 65,404,928 | Rust |
| E1 代码行数（SLOC） | 274 | 274 | 185 | Rust |
| E2 工具链复杂度（第三方依赖数） | 0 | 0 | 4 | Go, TinyGo |

#### 6.6.2 统计显著性汇总

| 指标 | Go vs Rust p 值 | TinyGo vs Rust p 值 | Go vs TinyGo p 值 | 显著性判定 |
|------|----------------|--------------------|--------------------|-----------|
| B1 R2 (1920×1080, K5) | 3.02×10⁻¹¹ | 3.02×10⁻¹¹ | 3.02×10⁻¹¹ | 全部 *** |
| B2 R2 (N=10000) | 3.00×10⁻¹¹ | 3.00×10⁻¹¹ | 0.663 | Go/Rust ***，TinyGo/Rust ***，Go/TinyGo n.s. |
| B3 R5 (16 MB) | 3.02×10⁻¹¹ | 3.02×10⁻¹¹ | 3.02×10⁻¹¹ | 全部 *** |
| B3 R5 (64 KB) | 3.02×10⁻¹¹ | 0.506 | 3.01×10⁻¹¹ | Go/Rust ***，TinyGo/Rust n.s.，Go/TinyGo *** |
| B4 R5 (N=10000) | 3.02×10⁻¹¹ | 3.02×10⁻¹¹ | 3.02×10⁻¹¹ | 全部 *** |

显著性判定标准：p < 0.05 为显著（*），p < 0.01 为高度显著（**），p < 0.001 为极其显著（***）。

### 6.7 本章小结

本章按照第 3 章定义的实验方案，依次完成了正确性验证、编译指标采集（C1、C2）、浏览器端性能测试（B1 的 R1–R3、B2 的 R1–R3）、WASI 端性能测试（B3 的 R4–R6、B4 的 R4–R6）、跨场景对比（B2 vs B4）以及工程效率评估（E1、E2）。实验共规划 20 幅图表（图 6-1 至图 6-20），涵盖柱状图、箱线图、折线图、散点图和雷达图五种可视化类型。Mann-Whitney U 检验结果表明，绝大多数工具链间的性能差异均达到极其显著水平（p < 0.001）；少数例外包括 B2（N=10000）的 Go 与 TinyGo 对比（p=0.663，不显著——尽管两者均值相差约 12%，但 TinyGo 因 GC 暂停导致标准差高达 8.0 ms，分布呈双峰形态，使得检验无法判定差异显著）以及 B3 R5（64 KB）的 TinyGo 与 Rust 对比（p≈0.506，不显著，两者在该输入规模下 SHA-256 性能几乎持平）。

---

## 第 7 章 总结与展望

### 7.1 研究总结

本文围绕"Go 与 Rust 在 WebAssembly 应用开发中的对比"这一课题，从理论调研、实验设计、代码实现到性能分析，系统地完成了以下工作：

1. **理论调研**：梳理了 WebAssembly 的核心原理和运行机制，研究了 Go（标准编译器、TinyGo）和 Rust 对接 WebAssembly 的技术体系，总结了两种语言在内存管理、编译后端和生态工具链方面的关键差异。

2. **实验设计**：基于 Hilbig 等人 [7]、Roadrunner [13]、Lumos [12] 等实证研究数据，选取了 4 个代表性测试用例（图像卷积 B1、JSON 往返 B2/B4、SHA-256 B3），覆盖浏览器端和微服务端两类典型场景、计算密集型和数据处理型两大负载模式。建立了包含 9 项定量指标和 1 项定性指标的评价体系。

3. **代码实现**：在统一的 Monorepo 项目中，使用 Go/TinyGo 和 Rust 分别实现了功能一致的算法模块和场景入口程序。Go 和 TinyGo 共享完全相同的源代码，Rust 使用 Cargo 工作空间组织共享算法库。三条工具链共编译生成 15 个 Wasm 二进制文件。

4. **测试框架**：设计并实现了基于 Playwright 的浏览器自动化测试框架和基于 hyperfine + 内部计时的 WASI 测试框架，通过进程级隔离、一致的启动参数和统计学设计的迭代策略（5 次预热 + 30 次测量）确保测量结果的可靠性和可复现性。

5. **性能分析**：从编译特性（二进制体积、构建时间）、运行性能（实例化时间、执行时间、内存占用）和工程效率（代码行数、工具链复杂度）三个维度对实验数据进行了系统分析，使用 Mann-Whitney U 检验验证差异的统计显著性。

### 7.2 主要结论

基于实验设计和分析框架，本文的主要结论和技术选型建议如下：

1. **二进制体积**：Rust 的 Wasm 产物体积最小，TinyGo 居中，Go 标准编译器最大。对于需要网络传输的浏览器端应用和对冷启动延迟敏感的 Serverless 场景，Rust 和 TinyGo 在体积方面具有显著优势。

2. **运行性能**：运行性能的优劣与负载类型密切相关，不存在单一的"最快"工具链。在**计算密集型场景**（图像卷积 B1、SHA-256 B3）中，TinyGo 凭借 LLVM 后端的循环优化在执行时间上**多数配置下优于 Rust**（卷积全部 8 种配置均快约 6%–11%；SHA-256 在 1 MB 和 16 MB 大输入下略快，但在 1 KB 和 64 KB 小输入下反而略慢于 Rust）。然而 TinyGo 的保守式 GC 导致**内存占用极高**（卷积场景下达 Rust 的 ~40 倍），在内存受限环境中需谨慎评估。在**数据处理场景**（JSON 往返 B2/B4）中，Rust 的 serde 编译时代码生成带来压倒性优势：浏览器端（B2）执行速度为 Go 的 3–8 倍、TinyGo 的 4–7 倍；WASI 端（B4）优势进一步扩大，为 Go 的 25–33 倍、TinyGo 的 9–10 倍。Go 标准编译器在绝大多数执行时间指标上为最慢，但在浏览器端 JSON 处理（B2）的小规模输入下反而略快于 TinyGo（N=100 时 Go 0.72 ms vs TinyGo 1.01 ms），原因在于 TinyGo 的保守式 GC 在频繁分配场景中更容易触发回收暂停。Go 的编译速度快、调试体验好的特点在开发迭代阶段具有独立价值。

3. **工程效率**：Go 和 TinyGo 的工具链更为简单——单一编译命令、无第三方依赖、较低的学习曲线。Rust 提供了更高的自动化程度（wasm-bindgen 自动类型转换），但构建步骤更多且依赖第三方 crate。对于快速原型开发和团队中 Go 经验丰富的场景，Go/TinyGo 可能是更务实的选择。

4. **生态健全性**：三条工具链在 WebAssembly 生态的成熟度存在显著差异。根据 State of WebAssembly 2023 调查 [5]，Rust 连续三年位居 WebAssembly 最常用语言首位，也是开发者最期望在未来使用的 Wasm 语言。Rust 的 Wasm 生态已形成完善的工具链闭环：wasm-bindgen 在 crates.io 上的累计下载量超过 2.9 亿次，拥有 3,600 余个反向依赖 [10]；web-sys 提供了覆盖全部浏览器 WebIDL 接口的自动生成绑定（累计下载超 2.2 亿次，反向依赖 2,300 余个）[29]；Wasmtime、Wasmer 等主流 Wasm 运行时本身也采用 Rust 编写。Web Almanac 2025 对 HTTP Archive 数据集的大规模分析进一步证实 [30]，在可识别源语言的 Wasm 模块中，Rust 占据约 1.5%–2.2% 的份额，是除 .NET/Blazor 和 Emscripten (C/C++) 之外最具代表性的系统语言。相比之下，Go/TinyGo 在真实 Web 部署中的份额不足 0.1% [30]，其 Wasm 生态仍处于发展阶段：浏览器端仅有底层的 `syscall/js` API 可用，缺少类似 wasm-bindgen 的自动化互操作工具；TinyGo 虽然在 WASI 和嵌入式场景表现出色，但其标准库兼容性有限（部分 `reflect`、`net/http` 等包不受支持），社区规模和第三方库数量均远小于 Rust 生态 [9]。Go 标准编译器的 Wasm 支持则由 Go 核心团队维护，稳定性有保障，但其浏览器端产物必须依赖官方 `wasm_exec.js` 胶水文件，灵活性不如 Rust 的 ES 模块生成方案。

5. **技术选型建议**：综合性能数据和生态成熟度，本文提出以下建议：
   - **浏览器端计算密集型应用**（如图像/视频处理、游戏引擎）：若优先考虑执行速度，TinyGo 是最佳选择（卷积性能最优），但需关注其内存占用和标准库兼容性限制；若优先考虑二进制体积、内存效率和生态工具链成熟度，Rust 更为均衡。
   - **浏览器端数据处理应用**（如 JSON 处理、文本分析）：推荐 Rust，执行速度领先 TinyGo 4–7 倍、内存占用最低，且 wasm-bindgen 和 web-sys 提供了最完善的浏览器 API 集成能力。
   - **微服务 / Serverless**：Rust 在冷启动和 JSON 类暖执行方面均具明显优势，且 Rust 编写的 Wasmtime 运行时是 WASI 生态的事实标准，两者的协同度最高；计算密集型负载下 TinyGo 暖执行性能与 Rust 相当甚至更优，但 Rust 的内存效率和冷启动速度仍然最佳。Go 标准编译器适合对编译速度要求高的 CI/CD 流程。
   - **快速原型验证**：Go 标准编译器的简洁性和编译速度适合初期探索，但需注意其产物体积较大（1.8–3.2 MB）可能不适合生产部署。

### 7.3 不足与展望

本研究存在以下局限性，也为后续工作指明了方向：

1. **测试场景覆盖**：本文选取了 4 个测试用例覆盖两大负载模式，但未涉及并发处理、网络 I/O 和文件系统操作等场景。未来可扩展到 Web Worker 并发、WASI HTTP 和数据库操作等更复杂的场景。

2. **工具链版本**：实验基于特定版本的编译器和运行时（Go 1.25.8、TinyGo 0.40.1、Rust 1.94.0、Wasmtime 33.0.0），随着 Go 标准编译器持续优化其 Wasm 后端、TinyGo 跟进 Go 版本更新、Rust 和 Wasmtime 引入组件模型支持，不同版本的实验结果可能存在差异。

3. **平台多样性**：实验仅在 macOS / Apple Silicon 平台上进行。不同 CPU 架构（x86-64）和操作系统（Linux）下的结果可能有所不同，尤其是 Wasmtime 的 Cranelift 后端在不同架构上的代码生成质量差异。

4. **WebAssembly 组件模型**：WASI Preview 2 和 WebAssembly 组件模型（Component Model）正在快速发展，Go 和 Rust 对组件模型的支持将是重要的后续研究方向。

5. **wasm-opt 优化**：本文未使用 Binaryen 项目的 `wasm-opt` 工具对编译产物进行二次优化。后续研究可评估 `wasm-opt` 对各工具链产物的体积和性能影响。

6. **多浏览器对比**：本文仅在 Chromium（V8 引擎）上进行浏览器端测试。不同浏览器引擎（SpiderMonkey / Firefox、JavaScriptCore / Safari）对 Wasm 的编译和执行策略不同，多浏览器对比有助于更全面地评估各工具链的浏览器兼容性。

---

## 参考文献

[1] Haas, A., Rossberg, A., Schuff, D. L., Titzer, B. L., et al. "Bringing the Web up to Speed with WebAssembly." *Proceedings of the 38th ACM SIGPLAN Conference on Programming Language Design and Implementation (PLDI)*, 2017. https://doi.org/10.1145/3062341.3062363

[2] WebAssembly Community Group. "WebAssembly consensus and end of Browser Preview." February 2017. https://lists.w3.org/Archives/Public/public-webassembly/2017Feb/0002.html

[3] W3C. "World Wide Web Consortium (W3C) brings a new language to the Web as WebAssembly becomes a W3C Recommendation." December 2019. https://www.w3.org/press-releases/2019/wasm/

[4] Bytecode Alliance. Wasmtime Documentation — WASI. https://docs.wasmtime.dev/

[5] Scott Logic. "The State of WebAssembly 2023." https://blog.scottlogic.com/2023/10/18/the-state-of-webassembly-2023.html

[6] Bytecode Alliance. "WASI Preview 2 and the WebAssembly Component Model." https://component-model.bytecodealliance.org/

[7] Hilbig, A., Lehmann, D., & Pradel, M. "An Empirical Study of Real-World WebAssembly Binaries: Security, Languages, Use Cases." *Proceedings of the Web Conference (WWW)*, 2021. https://doi.org/10.1145/3442381.3450138

[8] The Go Team. Go WebAssembly Documentation. https://go.dev/wiki/WebAssembly

[9] TinyGo Project. TinyGo Documentation. https://tinygo.org/docs/

[10] Rust and WebAssembly Working Group. wasm-bindgen. https://github.com/rustwasm/wasm-bindgen

[11] Jangda, A., Powers, B., Berger, E., Guha, A., & Larus, J. "Not So Fast: Analyzing the Performance of WebAssembly vs. Native Code." *USENIX Annual Technical Conference (ATC)*, 2019. https://www.usenix.org/conference/atc19/presentation/jangda

[12] Korvoj, M. et al. "Lumos: Performance Characterization of WebAssembly as a Serverless Runtime in the Edge-Cloud Continuum." arXiv:2510.05118, 2024. https://arxiv.org/abs/2510.05118

[13] "Roadrunner: Improving the Serverless Forwarding Layer for WebAssembly." arXiv:2511.01888, 2024. https://arxiv.org/abs/2511.01888

[14] Karnwong, K. "Native implementation vs WASM for Go, Python and Rust benchmark." December 2024. https://karnwong.me/posts/2024/12/native-implementation-vs-wasm-for-go-python-and-rust-benchmark/

[15] "Evaluating Legacy and Modern Cryptography on the Web: RSA, Hybrid AES and Ed25519 in Wasm and JavaScript." *Journal of Communications*, Vol. 20, No. 6, 2025. https://www.jocm.us/show-321-2118-1.html

[16] WebAssembly Community Group. WebAssembly Core Specification. https://webassembly.org/

[17] Bytecode Alliance. Wasmtime Documentation. https://docs.wasmtime.dev/

[18] The Go Team. "Go 1.21 Release Notes." August 2023. https://go.dev/doc/go1.21

[19] TinyGo Project. "Add support for GOOS=wasip1." Pull Request #3861. https://github.com/tinygo-org/tinygo/pull/3861

[20] Fermyon. "Shrink Your TinyGo WebAssembly Modules by 60%." https://www.fermyon.com/blog/optimizing-tinygo-wasm

[21] Crichton, A. "std: Add a new wasm32-unknown-unknown target." Rust Pull Request #45905, November 2017. https://github.com/rust-lang/rust/pull/45905

[22] "Performance evaluation of image convolution with WebAssembly." *SPIE Proceedings*, Vol. 12592, 2023. https://doi.org/10.1117/12.2667004

[23] The Rust Team. "Workspaces." *The Cargo Book*. https://doc.rust-lang.org/cargo/reference/workspaces.html

[24] Tolnay, D. et al. "serde — Serialization framework for Rust." https://serde.rs/

[25] Tolnay, D. et al. "serde_json — JSON support for Serde." https://github.com/serde-rs/json

[26] Bray, T. "The JavaScript Object Notation (JSON) Data Interchange Format." RFC 8259, IETF, December 2017. https://www.rfc-editor.org/rfc/rfc8259

[27] RustCrypto Contributors. "sha2 — SHA-2 hash functions." https://github.com/RustCrypto/hashes/tree/master/sha2

[28] RustCrypto Project. https://github.com/RustCrypto

[29] Rust and WebAssembly Working Group. "web-sys — Raw bindings to Web APIs." https://crates.io/crates/web-sys

[30] Vadgama, N., Demir, N., & Pollard, B. "WebAssembly." *The 2025 Web Almanac*, HTTP Archive, 2025. https://almanac.httparchive.org/en/2025/webassembly

[31] 黄文勇, 何良, 徐君. "WebAssembly 2023 年回顾与 2024 年展望." InfoQ, 2024. https://www.infoq.cn/article/5Zrq507bQW6lial5iVy1

[32] 柴树杉. "WebAssembly 这七年——从诞生到 WASM 原生时代." 知乎专栏, 2022. https://zhuanlan.zhihu.com/p/573136334

---

## 致谢

值此论文付梓之际，谨向我的指导老师致以最深切的谢忱。论文写作期间，承蒙老师悉心指点、不吝赐教，于治学之道启迪良多，获益匪浅。老师严谨笃实的学术风范与诲人不倦的师者襟怀，令我深受感佩，亦将铭记于心、受用终身。谨以此文，向所有在求学路上惠予关怀与鼓励的师长致以衷心的感谢。

---

## 附录

### 附录 A 核心算法源代码

#### A.1 Go 图像卷积实现（go/conv/conv.go）

```go
package conv

import "math"

var Kernel3 = [][]float64{
	{1, 2, 1}, {2, 4, 2}, {1, 2, 1},
}

var Kernel5 = [][]float64{
	{1, 4, 6, 4, 1}, {4, 16, 24, 16, 4}, {6, 24, 36, 24, 6},
	{4, 16, 24, 16, 4}, {1, 4, 6, 4, 1},
}

func KernelBySize(size int) [][]float64 {
	if size == 5 { return Kernel5 }
	return Kernel3
}

func Convolve(img []byte, w, h int, kernel [][]float64) []byte {
	kSize := len(kernel)
	kHalf := kSize / 2
	out := make([]byte, w*h*4)
	var kSum float64
	for _, row := range kernel {
		for _, v := range row { kSum += v }
	}
	if kSum == 0 { kSum = 1 }
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
				if val < 0 { val = 0 } else if val > 255 { val = 255 }
				out[idx+c] = byte(math.Round(val))
			}
			out[idx+3] = img[idx+3]
		}
	}
	return out
}
```

#### A.2 Rust 图像卷积实现（rust/shared/src/conv.rs）

```rust
pub const KERNEL3: &[&[f64]] = &[
    &[1.0, 2.0, 1.0], &[2.0, 4.0, 2.0], &[1.0, 2.0, 1.0],
];
pub const KERNEL5: &[&[f64]] = &[
    &[1.0, 4.0, 6.0, 4.0, 1.0], &[4.0, 16.0, 24.0, 16.0, 4.0],
    &[6.0, 24.0, 36.0, 24.0, 6.0], &[4.0, 16.0, 24.0, 16.0, 4.0],
    &[1.0, 4.0, 6.0, 4.0, 1.0],
];

pub fn kernel_by_size(size: usize) -> &'static [&'static [f64]] {
    if size == 5 { KERNEL5 } else { KERNEL3 }
}

pub fn convolve(img: &[u8], w: usize, h: usize, kernel: &[&[f64]]) -> Vec<u8> {
    let k_size = kernel.len();
    let k_half = k_size / 2;
    let mut out = vec![0u8; w * h * 4];
    let k_sum: f64 = kernel.iter().flat_map(|row| row.iter()).sum();
    let k_sum = if k_sum == 0.0 { 1.0 } else { k_sum };
    for y in 0..h {
        for x in 0..w {
            let idx = (y * w + x) * 4;
            for c in 0..3usize {
                let mut sum = 0.0f64;
                for ky in 0..k_size {
                    for kx in 0..k_size {
                        let iy = y as isize + ky as isize - k_half as isize;
                        let ix = x as isize + kx as isize - k_half as isize;
                        if iy >= 0 && iy < h as isize && ix >= 0 && ix < w as isize {
                            sum += img[(iy as usize * w + ix as usize) * 4 + c]
                                as f64 * kernel[ky][kx];
                        }
                    }
                }
                out[idx + c] = (sum / k_sum).round().clamp(0.0, 255.0) as u8;
            }
            out[idx + 3] = img[idx + 3];
        }
    }
    out
}
```

#### A.3 Go JSON 往返处理实现（go/jsonrt/jsonrt.go）

```go
package jsonrt

import ("encoding/json"; "sort")

type User struct {
	ID    int     `json:"id"`
	Name  string  `json:"name"`
	Email string  `json:"email"`
	Age   int     `json:"age"`
	Score float64 `json:"score"`
}

func Process(input []byte) ([]byte, error) {
	var users []User
	if err := json.Unmarshal(input, &users); err != nil { return nil, err }
	var filtered []User
	for _, u := range users {
		if u.Age >= 18 { filtered = append(filtered, u) }
	}
	sort.Slice(filtered, func(i, j int) bool {
		if filtered[i].Score != filtered[j].Score {
			return filtered[i].Score > filtered[j].Score
		}
		return filtered[i].ID < filtered[j].ID
	})
	return json.Marshal(filtered)
}
```

#### A.4 Rust JSON 往返处理实现（rust/shared/src/jsonrt.rs）

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    pub id: i64, pub name: String, pub email: String,
    pub age: i64, pub score: f64,
}

pub fn process(input: &[u8]) -> Result<Vec<u8>, String> {
    let users: Vec<User> =
        serde_json::from_slice(input).map_err(|e| format!("deserialize: {e}"))?;
    let mut filtered: Vec<User> =
        users.into_iter().filter(|u| u.age >= 18).collect();
    filtered.sort_by(|a, b| {
        b.score.partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.id.cmp(&b.id))
    });
    serde_json::to_vec(&filtered).map_err(|e| format!("serialize: {e}"))
}
```

### 附录 B 实验执行命令

```bash
# 1. 生成测试数据
make testdata

# 2. 编译所有 Wasm 模块（15 个）
make clean && make all

# 3. 正确性验证
make verify

# 4. 执行全部基准测试
make bench
# 等价于依次执行：
#   make bench-build     # 构建时间测量（5 次清洁构建）
#   make bench-wasi      # WASI 基准（hyperfine + 内部计时）
#   make bench-browser   # 浏览器基准（Playwright 自动化）

# 5. 查看二进制体积
make sizes
```

### 附录 C Makefile 编译目标汇总

| 目标 | 功能 | 输出 |
|------|------|------|
| `make go` | Go 标准编译器编译 5 个 Wasm 模块 | `build/*-go.wasm` |
| `make tinygo` | TinyGo 编译 5 个 Wasm 模块 | `build/*-tinygo.wasm` |
| `make rust` | Rust 编译 5 个 Wasm 模块 + wasm-bindgen 后处理 | `build/*-rust.wasm` |
| `make all` | 编译全部 15 个模块 | `build/` |
| `make testdata` | 生成测试数据和参考输出 | `testdata/` |
| `make verify` | 正确性验证 | 终端输出 PASS/FAIL |
| `make sizes` | 统计二进制体积 | 终端输出 |
| `make bench` | 执行全部基准测试 | `results/` |
| `make clean` | 清除编译产物 | — |
