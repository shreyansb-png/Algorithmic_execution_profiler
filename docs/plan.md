# Algorithmic Execution Profiler: Project Plan

> **Course:** CS207 | **Status:** 🚧 Work in progress | **Last updated:** 2026-10-30

## Table of Contents

1. [Overview](#1-overview)
2. [Goals and Non-Goals](#2-goals-and-non-goals)
3. [How It Works](#3-how-it-works)
4. [Key Design Decisions](#4-key-design-decisions)
5. [Phases and Tasks](#5-phases-and-tasks)
6. [Workloads to Measure](#6-workloads-to-measure)
7. [Analysis Methodology](#7-analysis-methodology)
8. [Testing and Validation](#8-testing-and-validation)
9. [Risks and Mitigations](#9-risks-and-mitigations)
10. [Timeline](#10-timeline)
11. [Stretch Goals](#11-stretch-goals)
12. [Planned Repository Structure](#12-planned-repository-structure)
13. [Progress Tracker](#13-progress-tracker)
14. [References](#14-references)

---

## 1. Overview

Big-O notation describes how the cost of an algorithm grows as its input size **N** grows. In practice, cost is usually measured as wall-clock time, and that measurement is noisy. It is affected by operating system scheduling, background programs, CPU frequency scaling, caches, and branch prediction.

This project removes that noise. Algorithms are written in **Jack** (the high-level language from nand2tetris), compiled down to **Hack machine code**, and executed on a **custom C++ emulator** of the 16-bit Hack computer. The Hack computer has no cache, no pipeline, and no interrupts, and every instruction takes exactly one cycle. This means:

- The same program with the same input always gives the **same cycle count**.
- One run per input size is enough, because there is no run-to-run noise.
- The measured curve reflects the **algorithm and compiler**, not the laptop it ran on.

A Python script then fits mathematical models to the measured data to test whether the observed growth matches the theoretical complexity class.

---

## 2. Goals and Non-Goals

### Goals

- [ ] Build a working pipeline from Jack source code to cycle counts
- [ ] Write a C++ Hack emulator that counts executed instructions exactly
- [ ] Measure at least 6 algorithms across different complexity classes
- [ ] Fit and compare candidate complexity models statistically
- [ ] Produce clear plots that show measured cycles against theory
- [ ] Make the whole project reproducible with a few commands
- [ ] Document the method, results, and limitations honestly

### Non-Goals

- Measuring real hardware performance (this is a model of an abstract machine)
- Gate-level or transistor-level simulation (the emulator is instruction-accurate only)
- Writing a new compiler or assembler (the official nand2tetris tools are used)
- Supporting very large inputs (the 16-bit architecture limits N)

---

## 3. How It Works

```
 Jack source (N set per run)
          |
          v
 [ Jack Compiler ]    .jack -> .vm    (high-level code to stack-machine code)
          |
          v
 [ VM Translator ]    .vm -> .asm     (stack operations to Hack assembly)
          |
          v
 [ Assembler ]        .asm -> .hack   (assembly to 16-bit binary)
          |
          v
 [ C++ Emulator ]     runs the binary, counts cycles, writes JSON/CSV
          |
          v
 [ Python Analysis ]  fits models, compares them, draws plots
```

| Stage | Input | Output | Purpose |
|---|---|---|---|
| Jack workload | algorithm + N | `.jack` | The code whose cost is being measured |
| Compiler | `.jack` | `.vm` | Lowers objects, loops, and arrays to stack operations |
| VM translator | `.vm` | `.asm` | Lowers stack operations to A/D register instructions |
| Assembler | `.asm` | `.hack` | Resolves labels and produces 16-bit machine code |
| Emulator | `.hack` | metrics file | Executes instructions and counts them exactly |
| Analysis | CSV of (N, cycles) | plots and tables | Tests which complexity class fits |

---

## 4. Key Design Decisions

### 4.1 Definition of a "cycle"
One **cycle** is one executed Hack instruction, whether an A-instruction or a C-instruction. Cycles are only counted inside the **region of interest** (see 4.4).

### 4.2 Hack memory map (reference)

| RAM address | Purpose |
|---|---|
| 0 to 4 | SP, LCL, ARG, THIS, THAT |
| 5 to 12 | temp segment |
| 13 to 15 | general-purpose registers |
| 16 to 255 | static variables |
| 256 to 2047 | stack |
| 2048 to 16383 | heap (used by `Array.new`, `Memory.alloc`) |
| 16384 to 24575 | screen memory-map |
| 24576 | keyboard memory-map |

### 4.3 Passing the input size N
Two options are being considered:

1. **Generate the Jack file from a template** with N written as a constant. This is simple, and compiling is cheap.
2. **Have the emulator write N into a fixed RAM address** before the program starts. Avoid addresses in the heap range.

Starting choice: **option 1**. Revisit later.

### 4.4 Region of interest (ROI)
Jack OS start-up (`Sys.init`) costs a large, constant number of cycles that would distort small-N measurements. The Jack code will write to special addresses to mark where measurement starts and stops, and the emulator will count only the cycles in between.

| Address (proposed) | Meaning |
|---|---|
| 24577 | ROI start |
| 24578 | ROI end |
| 24579 | Halt the emulator |

These are emulator-defined ports and are not part of the standard Hack hardware.

### 4.5 Termination and safety
- The emulator stops when the halt port is written.
- A **watchdog** stops the run after a maximum cycle count, so a buggy program cannot loop forever.

### 4.6 Correctness check
Every workload writes its result to a known RAM address. The harness compares it against a Python reference implementation. A fast curve for a wrong algorithm is meaningless.

---

## 5. Phases and Tasks

### Phase 0: Setup
- [x] Create the GitHub repository
- [ ] Write the README and this plan
- [ ] Decide on the CSV/JSON output format
- [ ] Create the folder structure (see section 12)

**Done when:** the repo has a README, a plan, and a clear folder layout.

### Phase 1: Toolchain
- [ ] Download the official nand2tetris software suite from nand2tetris.org
- [ ] Compile, translate, and run one small Jack program by hand
- [ ] Learn to read the generated `.vm`, `.asm`, and `.hack` files
- [ ] Write a script that runs the whole Jack-to-`.hack` pipeline in one command

**Done when:** a Jack program goes from source to `.hack` with a single command.

### Phase 2: Emulator core (C++)
- [ ] Model 32K words of ROM and 32K words of RAM
- [ ] Implement the A, D, and PC registers
- [ ] Load a `.hack` file (one 16-character binary line per instruction)
- [ ] Implement fetch, decode, and execute for A-instructions and C-instructions
- [ ] Implement all ALU operations, destinations, and jump conditions
- [ ] Add the halt port and the cycle watchdog
- [ ] Add a command-line option to set RAM values before the run
- [ ] Add a RAM dump option for debugging

**Done when:** final RAM contents match the official CPU emulator on several test programs.

### Phase 3: Instrumentation
- [ ] Count total cycles inside the region of interest
- [ ] Count A-instructions versus C-instructions
- [ ] Count jumps taken versus not taken
- [ ] Count RAM reads and writes, grouped by region (stack, heap, statics, screen)
- [ ] Track the stack high-water mark (maximum value of SP)
- [ ] Track cycles per function using a function-to-address map from the VM translator
- [ ] Write all metrics to a JSON file per run

**Done when:** one run produces a complete metrics file.

### Phase 4: Workloads and test harness
- [ ] Write Jack workloads (see section 6)
- [ ] Write Jack templates where N is a placeholder
- [ ] Write a Python harness that loops over N, builds, runs, verifies, and logs to CSV
- [ ] Use seeded random inputs so results are reproducible
- [ ] Verify every output against a Python reference

**Done when:** one command produces a CSV of (N, cycles) for every workload.

### Phase 5: Analysis
- [ ] Choose N values with geometric spacing (for example 8, 16, 32, 64, 128)
- [ ] Fit candidate models (see section 7)
- [ ] Compare models with AIC/BIC, not only R-squared
- [ ] Estimate the log-log slope with a confidence interval
- [ ] Plot normalized cost C(N)/f(N)
- [ ] Run a train-small, predict-large extrapolation test

**Done when:** each workload has a best-fit model backed by numbers and plots.

### Phase 6: Documentation and packaging
- [ ] Write the README with results and plots
- [ ] Write `docs/methodology.md`
- [ ] Write a "Limitations" section
- [ ] Add a one-command reproduction guide
- [ ] Add a license and credits

**Done when:** a stranger can clone the repo and reproduce the plots.

### Phase 7: Extensions (optional)
See section 11.

---

## 6. Workloads to Measure

| # | Algorithm | Expected complexity | Notes |
|---|---|---|---|
| 1 | Single array access | O(1) | Sanity baseline |
| 2 | Binary search | O(log N) | Sorted input |
| 3 | Linear scan / sum | O(N) | Simplest non-trivial case |
| 4 | Prefix sum | O(N) | Extra array writes |
| 5 | Merge sort | O(N log N) | Recursion plus allocation |
| 6 | Bubble sort | O(N^2) | Test best, worst, and random inputs |
| 7 | Insertion sort | O(N^2) worst, O(N) best | Shows input-dependent behavior |
| 8 | Matrix multiplication | O(N^3) | Small N only (memory limit) |
| 9 | Naive recursive Fibonacci | O(2^N) | N around 25 or less |

Input types to test where it matters: **sorted**, **reverse-sorted**, and **random** (seeded).

---

## 7. Analysis Methodology

### 7.1 Candidate models
Each workload's data is fitted against these shapes, with non-negative coefficients:

| Model | Form |
|---|---|
| Constant | `a` |
| Logarithmic | `a*log(N) + b` |
| Linear | `a*N + b` |
| Linearithmic | `a*N*log(N) + b` |
| Quadratic | `a*N^2 + b*N + c` |
| Cubic | `a*N^3 + b*N^2 + c*N + d` |
| Exponential | `a*2^N + b` |

### 7.2 Why R-squared is not enough
A quadratic can fit perfectly linear data (it just sets the N^2 coefficient close to 0), so a high R-squared only says a model is flexible. To decide which model is right, the project uses:

- **AIC/BIC**, which penalize extra parameters
- **Log-log slope**: on a log-log plot, O(N^k) appears as a straight line with slope k
- **Normalized cost** C(N)/f(N), which flattens to a constant when f is the right growth function
- **Extrapolation test**: fit on small N, predict large N, and compare with the real measurements

### 7.3 Plots to produce
- [ ] Cycles vs N (linear axes) for each workload
- [ ] Cycles vs N (log-log axes) with fitted slope
- [ ] Normalized cost C(N)/f(N) per workload
- [ ] All workloads on one log-log chart
- [ ] Best case vs worst case for sorting

---

## 8. Testing and Validation

- [ ] **Emulator vs official emulator:** compare final RAM on a set of test programs
- [ ] **Instruction tests:** one small test for each ALU operation and each jump condition
- [ ] **Algorithm correctness:** compare Jack output with a Python reference for every N
- [ ] **Determinism test:** run the same input twice and confirm identical cycle counts
- [ ] **Watchdog test:** confirm an infinite loop is stopped
- [ ] **Edge cases:** N = 0, N = 1, and the maximum supported N

---

## 9. Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| 16-bit integers (range -32768 to 32767) | Limits the largest N and can cause overflow | Choose N ranges carefully and check for overflow |
| Heap is only about 14K words | Large arrays and matrices will not fit | Keep matrix N small; reuse memory |
| Jack OS routines are not unit-cost | `*`, `/`, and `Memory.alloc` are loops, which hide extra cost | Use the per-function profile to separate them |
| Startup cost pollutes small N | Distorts the fit | Use the region-of-interest trigger |
| Emulator bugs | Wrong counts look like valid data | Compare against the official emulator |
| Wrong algorithm gives a clean curve | False confidence | Verify every output against a reference |
| Scope grows too large | Project may not finish | Finish phases 0 to 6 before any extension |
| Course rules on sharing solutions | Posting course solutions may be prohibited | Do not upload course project solutions; list the tools to download instead |

---

## 10. Timeline

Adjust these dates to match your deadline.

| Week | Focus | Output |
|---|---|---|
| 1 | Phase 0 and Phase 1 | Repo, plan, working toolchain |
| 2 | Phase 2 | Emulator runs programs correctly |
| 3 | Phase 3 | Metrics and region-of-interest trigger |
| 4 | Phase 4 | Workloads and harness, first CSV |
| 5 | Phase 5 | Fitting and first plots |
| 6 | Phase 5 and Phase 6 | All workloads analyzed, README results |
| 7 | Phase 6 | Final write-up, cleanup, reproducibility check |
| 8 | Buffer / Phase 7 | Extensions or fixes |

---

## 11. Stretch Goals

- [ ] **Function-level profile:** show how many cycles go to your algorithm versus `Math.multiply`, `Memory.alloc`, and so on
- [ ] **Space complexity:** stack high-water mark and heap words allocated
- [ ] **Best/worst/average case study:** show why "O" depends on the input
- [ ] **Compiler-effect experiment:** hand-optimize the generated code and show that constants change but the complexity class does not
- [ ] **Differential testing:** generate random small programs and compare the emulator with the official one
- [ ] **Cache model:** replay the memory-access trace through a simulated cache to study locality (for example row-major versus column-major traversal)
- [ ] **Heatmap viewer:** visualize RAM activity over time
- [ ] **Continuous integration:** run emulator tests automatically on every push

---

## 12. Planned Repository Structure

```
Algorithmic_execution_profiler/
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   ├── plan.md              <- this file
│   ├── architecture.md
│   └── methodology.md
├── jack/
│   ├── templates/           <- Jack files with an N placeholder
│   └── workloads/
├── emu/                     <- C++ emulator source and tests
├── tools/                   <- notes on downloading nand2tetris tools
├── harness/                 <- Python scripts that build, run, verify
├── analysis/                <- fitting and plotting scripts
└── results/
    ├── data/                <- CSV/JSON results
    └── plots/               <- PNG figures
```

---

## 13. Progress Tracker

| Phase | Description | Status |
|---|---|---|
| 0 | Setup | 🟨 In progress |
| 1 | Toolchain | ⬜ Not started |
| 2 | Emulator core | ⬜ Not started |
| 3 | Instrumentation | ⬜ Not started |
| 4 | Workloads and harness | ⬜ Not started |
| 5 | Analysis | ⬜ Not started |
| 6 | Documentation | ⬜ Not started |
| 7 | Extensions | ⬜ Not started |

Legend: ⬜ not started, 🟨 in progress, ✅ done

---

## 14. References

- Nisan, N. and Schocken, S. *The Elements of Computing Systems* (2nd ed.), MIT Press, 2021
- nand2tetris course and software: https://www.nand2tetris.org
- Cormen, Leiserson, Rivest, Stein. *Introduction to Algorithms*
- Sedgewick, R. and Wayne, K. *Algorithms* (empirical analysis of running time)
- Burnham, K. and Anderson, D. *Model Selection and Multimodel Inference* (AIC)

**Note:** this project simulates an abstract machine at the instruction level. Results describe the behavior of algorithms on the Hack architecture and do not claim to measure real hardware or transistor-level behavior.
