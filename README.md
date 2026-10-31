# Algorithmic Execution Profiler: Project Plan and Methodology

**Course:** CS207 | **Status:** ✅ Measurement pipeline and emulator complete (phase-by-phase status in Section 13) | **Last updated:** 2026-10-31

---

## Table of Contents
1. [Overview](#1-overview)
2. [Goals and Non-Goals](#2-goals-and-non-goals)
3. [How It Works](#3-how-it-works)
4. [Key Design Decisions](#4-key-design-decisions)
5. [Phases and Tasks](#5-phases-and-tasks)
6. [Workloads to Measure](#6-workloads-to-measure)
7. [Analysis Methodology](#7-analysis-methodology)
8. [Testing and Validation](#8-testing-and-validation)
9. [Risks, Mitigations and Limitations](#9-risks-mitigations-and-limitations)
10. [Order of Work](#10-order-of-work)
11. [Future Work](#11-future-work)
12. [Repository Structure](#12-repository-structure)
13. [Progress Tracker](#13-progress-tracker)
14. [How to Run a Measurement](#14-how-to-run-a-measurement)
15. [Validation Results](#15-validation-results)
16. [References](#16-references)

---

## 1. Overview

Big-O notation describes how the cost of an algorithm grows as its input size $N$ grows. In practice, cost is usually measured as wall-clock time, and that measurement is noisy. It is affected by operating system scheduling, background programs, CPU frequency scaling, caches, and branch prediction.

This project removes that noise. Algorithms are written in Jack (the high-level language from nand2tetris), compiled down to Hack machine code, and executed on a custom C++ emulator of the 16-bit Hack computer. The Hack computer has no cache, no pipeline, and no interrupts, and every instruction takes exactly one cycle. This means:

- The same program with the same input always gives the same cycle count.
- One run per input size is enough, because there is no run-to-run noise.
- The measured curve reflects the algorithm and compiler, not the laptop it ran on.

A statistical analysis (Section 7) then fits mathematical models to the measured data to test whether the observed growth matches the theoretical complexity class.

---

## 2. Goals and Non-Goals

### Goals
- Build a working pipeline from Jack source code to cycle counts.
- Write a C++ Hack emulator that counts executed instructions exactly.
- Measure algorithms across different complexity classes (status in Section 6).
- Fit and compare candidate complexity models statistically.
- Produce clear plots that show measured cycles against theory.
- Make the measurement reproducible (Section 14).
- Document the method, results, and limitations honestly.

### Non-Goals
- Measuring real hardware performance (this is a model of an abstract machine).
- Gate-level or transistor-level simulation (the emulator is instruction-accurate only).
- Writing a new compiler or assembler. The official nand2tetris Jack compiler and assembler are used. The VM translator is the C++ implementation written for the CS207 course.
- Supporting very large inputs (the 16-bit architecture limits $N$).

---

## 3. How It Works

```
 Jack source (Main.jack with N as a constant, plus Sys.jack)
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
 [ C++ Emulator ]     runs the binary, counts cycles, prints one CSV line
          |
          v
 [ Analysis ]         fits models, compares them, draws plots (Section 7)
```

| Stage | Input | Output | Purpose |
| :--- | :--- | :--- | :--- |
| **Jack workload** | algorithm + $N$ | `.jack` | The code whose cost is being measured |
| **Compiler** | `.jack` | `.vm` | Lowers objects, loops, and arrays to stack operations |
| **VM translator** | `.vm` | `.asm` | Lowers stack operations to A/D register instructions, adds the bootstrap code |
| **Assembler** | `.asm` | `.hack` | Resolves labels and produces 16-bit machine code |
| **Emulator** | `.hack` | CSV line | Executes instructions and counts them exactly |
| **Analysis** | CSV of ($N$, cycles) | plots and tables | Tests which complexity class fits |

---

## 4. Key Design Decisions

### 4.1 Definition of a "cycle"
One cycle is one executed Hack instruction, whether an A-instruction or a C-instruction. The cycles reported for a workload are only those inside the region of interest (Section 4.4). The emulator also keeps the total for the whole run, which includes start-up code.

### 4.2 Hack memory map (reference)

| RAM Address | Purpose |
| :--- | :--- |
| `0` to `4` | `SP`, `LCL`, `ARG`, `THIS`, `THAT` |
| `5` to `12` | temp segment |
| `13` to `15` | general-purpose registers |
| `16` to `255` | static variables |
| `256` to `2047` | stack |
| `2048` to `16383` | heap (used by `Array.new`, `Memory.alloc`) |
| `16384` to `24575` | screen memory-map (unused here, because no `Screen` or `Output` code is linked; used as scratch space for results) |
| `24576` | keyboard memory-map |
| `24577` | **emulator port:** ROI start |
| `24578` | **emulator port:** ROI end |
| `24579` | **emulator port:** halt |

*The three ports are emulator-defined and are not part of the standard Hack hardware. The emulator's RAM is therefore 24,580 words.*

### 4.3 Passing the input size N
Two options were considered:
1. Write $N$ into the Jack source as a constant (for example the loop limit). This is simple, and compiling is cheap.
2. Have the emulator write $N$ into a fixed RAM address before the program starts (`--ram-init`). Avoid addresses in the heap range.

**Chosen: option 1.** Option 2 is implemented in the emulator but is not required by the current workloads.

### 4.4 Region of interest (ROI)
Jack OS start-up costs a large, constant number of cycles that would distort small-$N$ measurements. The Jack code writes a non-zero value to a special address to mark where measurement starts and another to mark where it stops. The emulator zeroes its counters at the start write and freezes them at the end write.

| Address | Meaning |
| :--- | :--- |
| `24577` | ROI start |
| `24578` | ROI end |
| `24579` | Halt the emulator |

In Jack, the ports are reached through an `Array` variable pointed at the first port address. This compiles to a few inline instructions with no function call, so the marker overhead stays small:

```
var Array port;
let port = 24577;      // port[0] = ROI start, port[1] = ROI end
...
let port[0] = 1;       // ROI START
...algorithm...
let port[1] = 1;       // ROI END
```

Exact counting rules:
- The instruction that writes the start port is **not** counted. Counting begins with the next instruction.
- The instruction that writes the end port **is** counted, and counting stops after it.
- The Jack statement that writes the end port compiles to a number of instructions before the store (the exact number depends on the VM translator). This adds a small constant to every measurement, the same for every $N$. It is absorbed by the constant term in the fitted models and cancels in differences between runs.
- A program that never writes the start port is counted from the first instruction to the halt, as if the whole run were the region.
- An end-port write without an earlier start-port write is ignored. A start without an end produces a warning.

### 4.5 Termination and safety
- The emulator stops when a non-zero value is written to the halt port (`24579`). The minimal `Sys.jack` does this after `Main.main` returns.
- The emulator also stops if the program counter runs past the loaded program, or if a hand-written assembly program reaches the single-instruction self-jump idiom (`@X` then `0;JMP` to itself).
- A **watchdog** stops the run after one billion cycles. If the program has not halted by then, the emulator prints an error and exits with **code 2**, so an unfinished run can never be mistaken for a valid measurement.

### 4.6 Correctness check
Each workload stores its result at a known RAM address (`16384` for the current workload). The emulator option `--peek <address>` prints that value after the run, and it is compared against a reference value computed independently. For example, the sum of the numbers 1 to 40 must be 820. A fast curve for a wrong algorithm is meaningless.

### 4.7 Runtime: a minimal operating system
The full Jack OS does not fit in the Hack ROM (32,768 instructions) when translated by a straightforward VM translator: the official assembler rejected the program as too large. Because the font tables, screen code, and keyboard code are also irrelevant to algorithm measurements and add a large fixed start-up cost, the project links only:

- `Array.vm`, `Memory.vm`, `Math.vm` from the official OS.
- A custom `Sys.jack` whose `Sys.init` calls `Memory.init`, `Math.init`, then `Main.main`, and finally writes the halt port. `Sys.halt` and `Sys.error` also write the halt port.

`Output`, `Screen`, `String`, and `Keyboard` are not linked, so workloads cannot print. Results are read with `--peek` instead.

### 4.8 What the emulator reports
One CSV line on standard output: `N,cycles,reads,writes`, all counted inside the ROI.

| Field | Meaning |
| :--- | :--- |
| `N` | The first value loaded with `--ram-init`, or `0` when `--ram-init` is not used. The analysis step must record $N$ itself. |
| `cycles` | Instructions executed inside the ROI |
| `reads` | Reads of `M` (RAM at address `A`) as an ALU operand |
| `writes` | Writes to `M` from a destination field |

Optional values requested with `--peek`, and notes about the ROI, go to standard error so the CSV line stays clean.

---

## 5. Phases and Tasks

### Phase 0: Setup
- [x] Create the GitHub repository
- [x] Write the `README.md` and this plan
- [x] Decide on the output format (one CSV line: `N,cycles,reads,writes`)
- [x] Create the folder structure (see Section 12)  

*Done when: the repo has a README, a plan, and a clear folder layout.*

### Phase 1: Toolchain
- [x] Download the official nand2tetris software suite from nand2tetris.org
- [x] Compile, translate, and run one small Jack program by hand
- [x] Learn to read the generated `.vm`, `.asm`, and `.hack` files
- [ ] Write a script that runs the whole Jack-to-`.hack` pipeline in one command (the three steps are run by hand, see Section 14)  

*Done when: a Jack program goes from source to `.hack`. Met by hand; single-command automation is future work.*

### Phase 2: Emulator core (C++)
- [x] Model 32K words of ROM and the Hack RAM map (plus three emulator ports)
- [x] Implement the A, D, and PC registers
- [x] Load a `.hack` file (one 16-character binary line per instruction)
- [x] Implement fetch, decode, and execute for A-instructions and C-instructions
- [x] Implement all ALU operations, destinations, and jump conditions
- [x] Add the halt port and the cycle watchdog
- [x] Add a command-line option to set RAM values before the run (`--ram-init`)
- [x] Add a RAM inspection option (`--peek <address>`)  

*Done when: results are correct on test programs. Verified against hand-calculated cycle counts and results (Section 15). A side-by-side comparison with the official CPU Emulator was not performed.*

### Phase 3: Instrumentation
- [x] Count total cycles inside the region of interest
- [ ] Count A-instructions versus C-instructions
- [ ] Count jumps taken versus not taken
- [x] Count RAM reads and writes (totals only, not grouped by region)
- [ ] Track the stack high-water mark (maximum value of SP)
- [ ] Track cycles per function using a function-to-address map from the VM translator
- [ ] Write all metrics to a JSON file per run (the emulator prints a CSV line instead)  

*Done when: one run produces a complete metrics file. Partly met: one run produces cycles, reads, and writes.*

### Phase 4: Workloads and test harness
- [x] Write a Jack workload (linear sum loop with ROI markers, Section 6)
- [ ] Write the remaining workloads
- [ ] Write Jack templates where $N$ is a placeholder (currently $N$ is edited by hand in `Main.jack`)
- [ ] Write a Python harness that loops over $N$, builds, runs, verifies, and logs to CSV
- [ ] Use seeded random inputs so results are reproducible
- [x] Verify the output against a reference (sum of 1 to 40 is 820, checked with `--peek`)  

*Done when: one command produces a CSV of ($N$, cycles) for every workload.*

### Phase 5: Analysis
- [ ] Choose $N$ values with geometric spacing (for example $8, 16, 32, 64, 128$)
- [ ] Fit candidate models (see Section 7)
- [ ] Compare models with AIC/BIC, not only $R^2$
- [ ] Estimate the log-log slope with a confidence interval
- [ ] Plot normalized cost $C(N)/f(N)$
- [ ] Run a train-small, predict-large extrapolation test  

*Done when: each workload has a best-fit model backed by numbers and plots.*

### Phase 6: Documentation and packaging
- [x] Write this methodology document
- [ ] Write the `README.md` with results and plots
- [x] Write a "Limitations" section (Section 9)
- [x] Write a reproduction guide (Section 14)
- [ ] Add a `LICENSE` file (credits are in Section 16)  

*Done when: a stranger can clone the repo and reproduce the plots.*

### Phase 7: Extensions (optional)
See Section 11.

---

## 6. Workloads to Measure

| # | Algorithm | Expected Complexity | Notes | Status |
| :--- | :--- | :--- | :--- | :---: |
| 1 | Single array access | $O(1)$ | Sanity baseline | ⬜ |
| 2 | Binary search | $O(\log N)$ | Sorted input | ⬜ |
| 3 | Linear scan / sum | $O(N)$ | Simplest non-trivial case. Implemented as a sum loop (`jack/sum_loop/Main.jack`) | ✅ |
| 4 | Prefix sum | $O(N)$ | Extra array writes | ⬜ |
| 5 | Merge sort | $O(N \log N)$ | Recursion plus allocation | ⬜ |
| 6 | Bubble sort | $O(N^2)$ | Test best, worst, and random inputs. The $O(N)$ best case needs an early-exit flag | ⬜ |
| 7 | Insertion sort | $O(N^2)$ worst, $O(N)$ best | Shows input-dependent behavior | ⬜ |
| 8 | Matrix multiplication | $O(N^3)$ | Small $N$ only (memory limit) | ⬜ |
| 9 | Naive recursive Fibonacci | $O(2^N)$ | $N$ around 25 or less | ⬜ |

*Input types to test where it matters: sorted, reverse-sorted, and random (seeded).*

---

## 7. Analysis Methodology

The objective of this analysis is to experimentally determine the time complexity of each workload by studying how its computational cost changes with increasing input size. Instead of assuming the theoretical complexity beforehand, we measure the actual cycles consumed by each workload and fit the resulting measurements against several candidate mathematical growth functions.

The methodology consists of the following stages:
1. Collect cycle measurements for different input sizes.
2. Fit candidate mathematical models to the measured data.
3. Evaluate model quality using statistical criteria.
4. Examine growth rates using log-log plots, doubling ratios, and normalized cost.
5. Validate the models through extrapolation.
6. Compare experimental observations with theoretical complexity.

### 7.1 Performance Data Collection

Because the Hack computer has no caches, no pipeline, no interrupts, and no other programs running, the cycle count of a given program on a given input is **deterministic**. One run per input size is therefore enough. Repeated runs, warm-up executions, and medians, which are needed for wall-clock timing, are unnecessary and are not used. Determinism is instead checked directly by running the same program twice and confirming identical counts (Section 8).

Let:
- $N$ denote the input size.
- $C(N)$ denote the measured cycles inside the region of interest.
- $\widehat{C}(N)$ denote the cycles predicted by a fitted model.
- $m$ denote the total number of different input sizes tested.

A geometrically increasing sequence of input sizes is useful for identifying asymptotic growth patterns. For example:

$$
N = 8,\ 16,\ 32,\ 64,\ 128,\ 256,\ \ldots
$$

The usable range depends on the workload because of the 16-bit architecture and the memory limits in Section 9. Linear workloads can reach several hundred or a few thousand, quadratic workloads a few hundred, cubic matrix workloads about 60, and exponential workloads about 25. At least 8 input sizes per workload should be collected so that the model-selection criteria in Section 7.3 are meaningful.

For each input size:
- Build the program with that $N$.
- Run it once and record the cycles, reads, and writes inside the region of interest.
- Check the program's result against a reference value.
- Keep the compiler, translator, assembler, and emulator version fixed across the whole data set.

The measurements are stored in a structured dataset:

| Input Size ($N$) | Cycles (ROI) | RAM reads | RAM writes | Result check |
| :--- | :--- | :--- | :--- | :--- |
| $N_1$ | ... | ... | ... | pass/fail |
| $N_2$ | ... | ... | ... | pass/fail |
| $N_3$ | ... | ... | ... | pass/fail |

The measurement covers the workload itself, not OS start-up, input generation, or result storage, unless those operations are explicitly part of the workload.

### 7.2 Candidate Complexity Models

Each workload is fitted against several candidate mathematical functions. The objective is to determine which growth function best explains the observed measurements.

The candidate models are:

| Model | Mathematical Form | Expected Complexity |
| :--- | :--- | :--- |
| **Constant** | $C(N) = a$ | $O(1)$ |
| **Logarithmic** | $C(N) = a \ln N + b$ | $O(\log N)$ |
| **Linear** | $C(N) = aN + b$ | $O(N)$ |
| **Linearithmic** | $C(N) = aN \ln N + b$ | $O(N \log N)$ |
| **Quadratic** | $C(N) = aN^2 + bN + c$ | $O(N^2)$ |
| **Cubic** | $C(N) = aN^3 + bN^2 + cN + d$ | $O(N^3)$ |
| **Exponential** | $C(N) = a 2^N + b$ | $O(2^N)$ |

Here, $a, b, c, d$ are parameters estimated from the experimental measurements.

#### Parameter Constraints
The model should predict non-negative execution costs over the measured input range. For polynomial models, the leading coefficient should be positive for the usual increasing growth functions. Lower-order coefficients and constant offsets may be negative.

For example, the quadratic model:

$$
C(N) = aN^2 + bN + c
$$

does not require $b$ and $c$ to be non-negative. Imposing non-negative constraints on every coefficient can unnecessarily restrict the fitting process and produce inaccurate models.

#### Model Fitting Procedure
For each candidate model:
1. Substitute the measured input sizes into the mathematical expression.
2. Estimate the unknown parameters using least-squares regression.
3. Calculate the predicted execution cost for every input size.
4. Calculate the residual error between measured and predicted values.
5. Store the fitted parameters and model evaluation statistics.

The primary fitting objective is to minimize the Residual Sum of Squares ($RSS$):

$$
RSS = \sum_{i=1}^{m} \left( C(N_i) - \widehat{C}(N_i) \right)^2
$$

A lower $RSS$ indicates that the model fits the measured data more closely. All candidate models should be fitted using the same observations and response scale to ensure meaningful comparisons.

### 7.3 Why R-squared Alone Is Not Enough

A common method of evaluating regression models is the coefficient of determination, denoted by $R^2$. It is defined as:

$$
R^2 = 1 - \frac{\displaystyle\sum_{i=1}^{m} \left( C(N_i) - \widehat{C}(N_i) \right)^2}{\displaystyle\sum_{i=1}^{m} \left( C(N_i) - \overline{C} \right)^2}
$$

where:

$$
\overline{C} = \frac{1}{m} \sum_{i=1}^{m} C(N_i)
$$

An $R^2$ value close to $1$ indicates that the model explains a large proportion of the variation in the measured execution costs. However, a high $R^2$ does not necessarily mean that the selected complexity class is correct.

For example, a quadratic model $C(N) = aN^2 + bN + c$ can fit approximately linear data by assigning a very small value to $a$. Similarly, a cubic model can approximate quadratic or linear growth by making its higher-order coefficients sufficiently small. Therefore, a more flexible model may achieve a higher $R^2$ simply because it contains more parameters.

To avoid selecting unnecessarily complicated models, we combine $R^2$ with the following evaluation methods.

#### 7.3.1 Akaike Information Criterion (AIC)
AIC evaluates the trade-off between goodness of fit and model complexity. For least-squares regression with Gaussian residuals, the AIC can be expressed, ignoring a common additive constant, as:

$$
\boxed{AIC = m \ln\left(\frac{RSS}{m}\right) + 2k}
$$

where:
- $m$ is the number of observations.
- $RSS$ is the residual sum of squares.
- $k$ is the total number of estimated parameters, including the error variance.

A model with more parameters receives a larger complexity penalty.

**Interpretation:** Lower AIC values indicate a preferable balance between fitting accuracy and model complexity.

#### 7.3.2 Bayesian Information Criterion (BIC)
BIC is another model-selection criterion that penalizes unnecessary parameters. It is calculated as:

$$
\boxed{BIC = m \ln\left(\frac{RSS}{m}\right) + k \ln(m)}
$$

Here, $k$ again includes the estimated error variance. Unlike AIC, the penalty increases with the logarithm of the number of observations.

**Interpretation:** Among the candidate models, the model with the lowest BIC is preferred.

Both AIC and BIC should be calculated using the same observations and response scale. Their standard statistical interpretation also assumes an appropriate residual distribution, such as independent Gaussian errors with constant variance.

#### 7.3.3 Adjustments for deterministic, small-sample data
Two properties of this project's data need care when applying AIC and BIC:

- **The data has no measurement noise.** Residuals are not random scatter. They are systematic misfit between the model and the true cost function, so the Gaussian-noise assumption does not strictly hold. AIC and BIC are therefore used as a consistent ranking of candidate models, not as formal probabilities.
- **A perfect fit gives $RSS \approx 0$.** Then $\ln(RSS/m)$ is undefined or extremely negative. To keep the comparison meaningful, $RSS/m$ is floored at a tiny value relative to the data scale (for example $10^{-12}\,\overline{C}^{\,2}$), and exact fits are reported as such.
- **The number of sizes $m$ is small** (often 8 to 12), while $k$ reaches 5 for the cubic model. The small-sample corrected criterion should be used instead of plain AIC, and it requires $m > k + 1$:

$$
AIC_c = AIC + \frac{2k(k+1)}{m - k - 1}
$$

### 7.4 Log-Log Analysis

Log-log analysis is used to investigate polynomial growth rates. Suppose the execution cost follows:

$$
C(N) = aN^p
$$

Taking the natural logarithm on both sides:

$$
\ln C(N) = \ln a + p \ln N
$$

This is a linear equation of the form $y = mx + c$, where:

$$
y = \ln C(N), \quad x = \ln N
$$

Therefore, the slope of the log-log plot is:

$$
\boxed{p = \text{Log-Log Slope}}
$$

#### Expected Approximate Slopes

| Complexity | Expected Log-Log Slope |
| :--- | :--- |
| $O(1)$ | $0$ |
| $O(\log N)$ | Approaches $0$ |
| $O(N)$ | $1$ |
| $O(N \log N)$ | Approaches $1$ |
| $O(N^2)$ | $2$ |
| $O(N^3)$ | $3$ |

For every workload:
1. Transform the input sizes using $\ln N$.
2. Transform the measured cycles using $\ln C(N)$.
3. Plot $\ln C(N)$ against $\ln N$.
4. Fit a straight line to the transformed data.
5. Record the estimated slope.
6. Compare the estimated slope with the expected theoretical exponent.

The slope should preferably be estimated over larger input sizes, where constant and lower-order terms have less influence.

**Important Limitation:** Log-log analysis alone cannot reliably distinguish linear and linearithmic growth. For a linearithmic workload $C(N) = aN \ln N$, the local log-log slope is:

$$
1 + \frac{1}{\ln N}
$$

As $N$ increases:

$$
\lim_{N \to \infty} \left( 1 + \frac{1}{\ln N} \right) = 1
$$

Thus, the slope approaches $1$, just like a linear function. Similarly, an exponential workload does not produce a constant log-log slope. For exponential growth, a semi-log plot of $\ln C(N)$ against $N$ is a more suitable additional diagnostic.

#### Doubling ratio
When $N$ doubles from one measurement to the next, the ratio of costs approximates $2^p$:

$$
r = \frac{C(2N)}{C(N)} \approx 2^p
$$

| Ratio $r$ | Growth |
| :--- | :--- |
| about $1$ | $O(1)$ or $O(\log N)$ |
| about $2$ | $O(N)$ |
| slightly above $2$ | $O(N \log N)$ |
| about $4$ | $O(N^2)$ |
| about $8$ | $O(N^3)$ |

This diagnostic is only meaningful if fixed overhead has been removed, which is why the region of interest matters. In the unmeasured-start-up runs in Section 15, doubling the loop passes only raised the total cycle count by 15%, because about 85% of the run was start-up code. Inside a correctly placed region of interest, the same doubling approaches a ratio of 2.

### 7.5 Normalized Cost Analysis

Normalized cost provides another method of identifying the underlying growth rate. The main idea is to divide the measured execution cost by a candidate growth function. If the selected growth function correctly describes the workload, its normalized cost should approach a constant as the input size increases.

Define:

$$
\boxed{C_{\text{normalized}}(N) = \frac{C(N)}{f(N)}}
$$

where $f(N)$ is the candidate growth function.

#### Expected Normalization Functions

| Candidate Complexity | Normalized Cost |
| :--- | :--- |
| $O(1)$ | $C(N)$ |
| $O(\log N)$ | $\dfrac{C(N)}{\ln N}$ |
| $O(N)$ | $\dfrac{C(N)}{N}$ |
| $O(N \log N)$ | $\dfrac{C(N)}{N \ln N}$ |
| $O(N^2)$ | $\dfrac{C(N)}{N^2}$ |
| $O(N^3)$ | $\dfrac{C(N)}{N^3}$ |
| $O(2^N)$ | $\dfrac{C(N)}{2^N}$ |

For example, suppose the actual execution cost follows $C(N) = aN^2 + bN + c$. Dividing both sides by $N^2$:

$$
\frac{C(N)}{N^2} = a + \frac{b}{N} + \frac{c}{N^2}
$$

Taking the limit as $N$ approaches infinity:

$$
\boxed{\lim_{N \to \infty} \frac{C(N)}{N^2} = a}
$$

Therefore, a quadratic workload should exhibit approximately constant normalized cost when divided by $N^2$.

Similarly:
- Linear growth should flatten when divided by $N$.
- Linearithmic growth should flatten when divided by $N \ln N$.
- Cubic growth should flatten when divided by $N^3$.

For each workload, normalized-cost curves should be generated for the most relevant candidate complexity classes. The preferred normalization is the one that exhibits the most stable behavior over larger input sizes, rather than merely appearing flat at a few isolated measurements.

### 7.6 Extrapolation and Predictive Validation

A model that fits the existing measurements well may still fail to predict performance at larger input sizes. To test whether a model captures the actual growth pattern, an extrapolation experiment is performed.

The procedure is:
1. Divide the measured dataset into a training set and a validation set.
2. Use smaller input sizes for training.
3. Fit the candidate models using only the training measurements.
4. Predict execution costs at larger input sizes.
5. Compare the predictions with actual measured costs.
6. Calculate prediction errors for every model.

The relative prediction error is defined as:

$$
\boxed{E(N) = \frac{\vert C(N) - \widehat{C}(N) \vert}{C(N)} \times 100}
$$

A smaller prediction error indicates better predictive performance. The model should ideally be tested using multiple training and validation splits rather than relying on a single split.

For example:
- Train on the smallest $60\%$ of input sizes and validate on the remaining $40\%$.
- Train on the smallest $70\%$ and validate on the remaining $30\%$.
- Train on the smallest $80\%$ and validate on the remaining $20\%$.

This helps determine whether the selected model continues to predict the observed growth pattern beyond the range on which it was fitted.

*Extrapolation is an empirical validation technique, not a mathematical proof of asymptotic complexity. Predictions far beyond the measured range should be interpreted cautiously.*

### 7.7 Sorting: Best-Case vs Average-Case vs Worst-Case Analysis

Sorting algorithms can exhibit different performance depending on the initial arrangement of the input data. Therefore, sorting workloads should be analyzed using multiple input distributions.

The following cases should be considered:

| Case | Input Arrangement | Purpose |
| :--- | :--- | :--- |
| **Best case** | Already sorted | Measures performance on favorable input |
| **Average case** | Randomly shuffled | Measures typical performance |
| **Worst case** | Adversarial arrangement | Measures performance on unfavorable input |

For each input size $N$, collect the cycles for all three cases:

$$
C_{\text{best}}(N), \quad C_{\text{average}}(N), \quad C_{\text{worst}}(N)
$$

Plot all three measurements on the same graph, then fit candidate complexity models independently to each case. This allows us to investigate:
- Whether the algorithm is sensitive to input ordering.
- Whether its best and worst cases belong to different complexity classes.
- Whether random input behaves closer to the best or worst case.
- Whether the experimental results agree with the theoretical analysis of the sorting algorithm.

For algorithms such as insertion sort, different input orders can produce substantial differences in execution cost. For bubble sort, the best case is linear only if the implementation stops early when a pass makes no swaps. For algorithms such as merge sort, the asymptotic running time is generally $O(N \log N)$ across these arrangements, although constant factors may still differ.

The input-generation procedure must be documented so that best-case, average-case, and worst-case measurements are reproducible. Random inputs use a fixed seed.

### 7.8 Plots and Visualizations

The following plots will be generated for every workload to visualize and validate the measured growth patterns:

1. **Plot 1: Cycles vs Input Size (Linear Axes)**
   - **X-axis:** Input size $N$.
   - **Y-axis:** Measured cycles.
   - Plot the actual measurements and overlay the fitted candidate model to compare absolute execution costs and identify large deviations.

2. **Plot 2: Cycles vs Input Size (Log-Log Axes)**
   - **X-axis:** $\log N$.
   - **Y-axis:** $\log C(N)$.
   - Include a fitted straight-line trend where appropriate, display the estimated log-log slope, and compare it against the expected theoretical growth exponent.

3. **Plot 3: Normalized Cost vs Input Size**
   - Generate separate normalized-cost curves for relevant candidate functions:
     $$
     \frac{C(N)}{N}, \quad \frac{C(N)}{N \ln N}, \quad \frac{C(N)}{N^2}, \quad \frac{C(N)}{N^3}
     $$
   - Also include logarithmic and exponential normalizations where relevant to identify which normalization produces the most stable curve as $N$ increases.

4. **Plot 4: Comparison of All Workloads**
   - Display all workloads on a common log-log chart using consistent axis scaling and labels for each workload to compare estimated growth rates.

5. **Plot 5: Sorting Best Case vs Average Case vs Worst Case**
   - Plot all three input arrangements on the same graph, compare measured cycles, overlay fitted growth models, and examine whether input distribution changes the empirical growth rate or the main constant factor.

6. **Plot 6: Actual vs Predicted Cycles**
   - **X-axis:** Input size $N$.
   - **Y-axis:** Cycles.
   - Plot actual measured values and model predictions, clearly distinguishing training measurements from validation measurements to evaluate extrapolation accuracy.

### 7.9 Final Model Selection

The final complexity classification should not be determined by a single statistical score. Instead, each candidate model should be evaluated using combined evidence from:
1. **Goodness of fit:** Does the model closely match the measured cycles?
2. **AIC, AICc and BIC:** Does the model explain the data without unnecessary parameters?
3. **Log-log slope and doubling ratio:** Does the estimated growth exponent agree with the candidate complexity?
4. **Normalized cost:** Does dividing the measured cost by the proposed growth function produce a stable curve?
5. **Extrapolation:** Does the model predict larger input sizes accurately?
6. **Theoretical consistency:** Does the empirical result agree with the known structure of the workload?

#### Final Comparison Table Format

| Candidate Model | $R^2$ | AICc | BIC | Log-Log Slope | Validation Error |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Constant** | ... | ... | ... | ... | ... |
| **Logarithmic** | ... | ... | ... | ... | ... |
| **Linear** | ... | ... | ... | ... | ... |
| **Linearithmic** | ... | ... | ... | ... | ... |
| **Quadratic** | ... | ... | ... | ... | ... |
| **Cubic** | ... | ... | ... | ... | ... |
| **Exponential** | ... | ... | ... | ... | ... |

The final reported complexity should be the growth class consistently supported by the different evaluation methods. If multiple models remain plausible, the report should explicitly mention that the available measurements are insufficient to distinguish them reliably.

### 7.10 Expected Deliverables

The analysis phase should produce the following artifacts:
- Exact cycle, read, and write counts for every workload and input size (one deterministic run each).
- Fitted parameters for every candidate complexity model.
- $R^2$, $RSS$, $AIC_c$, and $BIC$ comparison tables.
- Log-log plots with estimated slopes, and doubling-ratio tables.
- Normalized-cost plots for competing growth functions.
- Actual-versus-predicted performance plots.
- Extrapolation and validation error tables.
- Best-case, average-case, and worst-case sorting comparisons.
- A final complexity classification for each workload.
- A comparison between empirical and theoretical complexity.

**Final Objective:** Establish a reproducible experimental methodology for determining algorithmic growth rates, rather than relying solely on theoretical assumptions or regression fit scores.

---

## 8. Testing and Validation

- [x] **Algorithm correctness:** the sum workload's result is read with `--peek` and compared with the reference value (820 for 40 passes).
- [x] **Exact cycle counts:** hand-assembled test programs with exactly calculable counts match the emulator (Section 15).
- [x] **Region-of-interest tests:** start only, end only, start and end, and no markers all behave as specified (Section 4.4).
- [x] **Halt-port test:** a program writing a non-zero value to the halt port stops immediately. Writing zero does not stop it.
- [x] **Watchdog test:** an infinite loop is stopped, prints an error, and exits with code 2.
- [x] **Linearity test:** a straight line fitted to two loop sizes predicted the cycle count of a third size exactly (Section 15).
- [ ] **Determinism test as a recorded check:** run the same input twice and confirm identical counts. Expected by design, not recorded as a separate test.
- [ ] **Emulator vs official CPU Emulator:** compare final RAM on a set of test programs.
- [ ] **Instruction tests:** one small test for each ALU operation and each jump condition. The decoding was reviewed against the Hack specification but not covered by a test suite.
- [ ] **Edge cases:** $N = 0$, $N = 1$, and the maximum supported $N$.

---

## 9. Risks, Mitigations and Limitations

| Risk | Why it matters | Mitigation | Outcome |
| :--- | :--- | :--- | :--- |
| **16-bit integers (range -32768 to 32767)** | Limits the largest $N$ and can cause overflow | Choose $N$ ranges carefully and check for overflow | Open: constrains $N$ ranges |
| **Heap is only about 14K words** | Large arrays and matrices will not fit | Keep matrix $N$ small; reuse memory | Open |
| **Jack OS routines are not unit-cost** | `*`, `/`, and `Memory.alloc` are loops, which hide extra cost | Per-function profile (future work) | Open |
| **Start-up cost pollutes small $N$** | Distorts the fit | Region-of-interest trigger | ✅ Resolved |
| **Emulator bugs** | Wrong counts look like valid data | Hand-calculated counts, result checks | 🟨 Partly mitigated; official-emulator comparison not done |
| **Wrong algorithm gives a clean curve** | False confidence | Check every result against a reference | ✅ Mitigated with `--peek` |
| **Scope grows too large** | Project may not finish | Unfinished items moved to Future Work | ✅ Handled |
| **Course rules on sharing solutions** | Posting course solutions may be prohibited | The VM translator is not uploaded; the setup lists what to download | ✅ Handled |
| **Full Jack OS too large for the ROM** | The assembler rejects programs over 32,768 instructions | Minimal OS: `Array`, `Memory`, `Math` plus a custom `Sys.jack` (Section 4.7) | ✅ Resolved |
| **Jack programs never reach a single-instruction halt loop** | The emulator would run to the cycle cap | Halt port written by `Sys.jack` | ✅ Resolved |
| **Runaway programs look like valid runs** | A capped run would poison the data | Error message and exit code 2 | ✅ Resolved |

### Limitations
- **Abstract machine, not hardware.** Results describe instruction counts on the Hack architecture. They say nothing about real CPU time, caches, or branch prediction.
- **Constants depend on the VM translator.** Each Jack statement expands into many Hack instructions, and how many depends on the translator. A different translator gives different constants (for example 126 cycles per loop pass here). The growth class does not change.
- **The OS is partial.** Workloads cannot print or draw, and results are read from RAM.
- **`N` in the CSV line is not reliable on its own.** It comes from the first `--ram-init` value and is `0` otherwise, so the analysis must record $N$ separately.
- **Small constant offset in the ROI.** The marker statements add a fixed handful of instructions to every measurement (Section 4.4).
- **Limited telemetry.** Instruction types, jump statistics, stack depth, and per-function costs are not collected.

---

## 10. Order of Work

The project was built in this order:

1. Created the repository, README, and plan.
2. Ran a small Jack program through the toolchain by hand (compiler, VM translator, assembler).
3. Wrote the C++ emulator: loader, fetch/decode/execute, ALU, jumps, cycle counter, reads and writes counters.
4. Found that Jack programs never reach a single-instruction halt loop, and added the halt port and the cycle-cap error exit.
5. Found that the full Jack OS does not fit in the ROM, and replaced it with a minimal OS and a custom `Sys.jack`.
6. Added `--peek` to check program results.
7. Added the region-of-interest ports so start-up is not counted.
8. Validated the cycle counts and linear growth on a sum loop (Section 15).

---

## 11. Future Work

**Not implemented from the original plan:**
- A single command for the Jack-to-`.hack` pipeline, and a harness that loops over $N$, builds, runs, verifies, and writes a CSV.
- Jack templates with an $N$ placeholder.
- Workloads 1, 2, 4 to 9 in Section 6.
- The full analysis in Section 7: fitting, model selection, log-log slopes, normalized cost, extrapolation, and plots.
- More telemetry: A versus C instruction counts, jumps taken, RAM traffic by region, stack high-water mark, per-function cycles, and a JSON metrics file.
- Comparison of the emulator with the official CPU Emulator on test programs, and a full instruction test suite.

**Stretch goals:**
- **Function-level profile:** show how many cycles go to the algorithm versus `Math.multiply`, `Memory.alloc`, and so on.
- **Space complexity:** stack high-water mark and heap words allocated.
- **Compiler-effect experiment:** hand-optimize the generated code and show that constants change but the complexity class does not.
- **Differential testing:** generate random small programs and compare the emulator with the official one.
- **Cache model:** replay the memory-access trace through a simulated cache to study locality, for example row-major versus column-major traversal.
- **Heatmap viewer:** visualize RAM activity over time.
- **Continuous integration:** run emulator tests automatically on every push.
- **Shared call and return routines in the VM translator**, which would shrink programs enough to link the full OS.

---

## 12. Repository Structure

```text
Algorithmic_execution_profiler/
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   └── project_plan.md      <- this file
├── jack/
│   ├── runtime/
│   │   └── Sys.jack         <- minimal Sys class (init, halt, error)
│   └── sum_loop/
│       └── Main.jack        <- linear sum workload with ROI markers
├── emu/
│   ├── cpu.hpp
│   ├── cpu.cpp
│   ├── telemetry.hpp
│   └── main.cpp
├── tools/                   <- notes on downloading the nand2tetris tools (optional)
├── harness/                 <- future: Python scripts that build, run, verify
├── analysis/                <- future: fitting and plotting scripts
└── results/                 <- future: CSV results and PNG figures
```

The nand2tetris software and the course VM translator are not part of the repository.

---

## 13. Progress Tracker

| Phase | Description | Status |
| :---: | :--- | :---: |
| **0** | Setup | ✅ Done |
| **1** | Toolchain | 🟨 Works by hand; one-command script outstanding |
| **2** | Emulator core | ✅ Done |
| **3** | Instrumentation | 🟨 Cycles, reads, writes, and ROI done |
| **4** | Workloads and harness | 🟨 One workload verified; harness outstanding |
| **5** | Analysis | ⬜ Not started |
| **6** | Documentation | 🟨 Methodology and run guide done; README results outstanding |
| **7** | Extensions | ⬜ Not started |

*Legend: ⬜ Not started, 🟨 Partly done, ✅ Done*

---

## 14. How to Run a Measurement

1. **Prepare one folder** (here called `hello`) containing `Main.jack`, `Sys.jack`, and the three OS files `Array.vm`, `Memory.vm`, and `Math.vm` copied from the nand2tetris `tools/OS` folder. Do not copy `Output.vm`, `Screen.vm`, `String.vm`, `Keyboard.vm`, or the original `Sys.vm`.
2. **Compile Jack to VM** from the nand2tetris `tools` folder:
   ```
   .\JackCompiler.bat "<path to hello>"
   ```
3. **Translate VM to assembly** with the course VM translator, run on the whole `hello` folder. It must write a single `.asm` file that includes the bootstrap code (set `SP` to 256, call `Sys.init`).
4. **Assemble** from the `tools` folder:
   ```
   .\Assembler.bat "<path to the .asm file>"
   ```
5. **Build the emulator** in the `emu` folder:
   ```
   g++ -std=c++17 -o profiler main.cpp cpu.cpp
   ```
   Adding `-O2` (the capital letter O, not a zero) makes it about four times faster.
6. **Run the program** and check its result:
   ```
   .\profiler.exe "<path to the .hack file>" --peek 16384
   ```

**Output.** Standard output holds one line: `N,cycles,reads,writes`. Standard error holds the `--peek` values and a note that the region of interest was used. The exit code is `0` on success, `1` for bad arguments or an unreadable file, and `2` if the program never halted.

To measure another input size, change the constant in `Main.jack` and repeat steps 2 to 4 and 6.

---

## 15. Validation Results

### 15.1 Sum loop through the full pipeline (start-up included)
These runs were made through the complete toolchain **before** the region-of-interest markers were added, so the counts include start-up code. Each loop pass computes `sum = sum + i` and `i = i + 1` and tests `i < limit`.

| Loop passes | Total cycles | RAM reads | RAM writes |
| :---: | :---: | :---: | :---: |
| 10 | 8,660 | 3,299 | 2,099 |
| 20 | 9,920 | 3,769 | 2,369 |
| 40 | 12,440 | not recorded | not recorded |

- Going from 10 to 20 passes adds exactly 1,260 cycles, so one pass costs **126 cycles** (47 reads, 27 writes).
- This gives $\text{cycles} = 126 \times \text{passes} + 7{,}400$. The model was fitted on the 10-pass and 20-pass runs and **predicted 12,440 cycles for 40 passes. The measured value was exactly 12,440.**
- About 7,400 cycles (85% of the 10-pass run) are fixed start-up cost. This is why the region of interest was added.
- **Correctness:** with 40 passes the program stores 820 at RAM address 16384 (the sum of 1 to 40), confirmed with `--peek 16384`.

### 15.2 Hand-assembled test programs (region of interest)
A loop with a known instruction count was run through the emulator, with the region-of-interest start before the loop and the end after it.

| $N$ | Expected cycles ($14N + 8$) | Measured | Expected reads ($5N + 2$) | Measured | Expected writes ($2N + 1$) | Measured |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 10 | 148 | 148 | 52 | 52 | 21 | 21 |
| 20 | 288 | 288 | 102 | 102 | 41 | 41 |
| 40 | 568 | 568 | 202 | 202 | 81 | 81 |

Other emulator checks: a program without region markers counts the whole run; an end marker without a start is ignored; a start without an end produces a warning; a runaway loop stops at the cycle cap with exit code 2; and a countdown program from 3 takes exactly 8 cycles.

---

## 16. References

- Nisan, N. and Schocken, S. *The Elements of Computing Systems* (2nd ed.), MIT Press, 2021.
- nand2tetris course and software: [https://www.nand2tetris.org](https://www.nand2tetris.org)
- Cormen, Leiserson, Rivest, Stein. *Introduction to Algorithms*.
- Sedgewick, R. and Wayne, K. *Algorithms* (empirical analysis of running time).
- Burnham, K. and Anderson, D. *Model Selection and Multimodel Inference* (AIC).

> **Note:** This project simulates an abstract machine at the instruction level. Results describe the behavior of algorithms on the Hack architecture and do not claim to measure real hardware or transistor-level behavior.
