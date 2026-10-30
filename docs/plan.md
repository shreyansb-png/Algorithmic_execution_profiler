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

The objective of this analysis is to determine the empirical time complexity of each workload by studying how its execution cost changes as the input size \(N\) increases.

Rather than assuming the theoretical complexity beforehand, we measure the actual number of CPU cycles consumed by each workload and compare the measurements against several candidate growth functions.

The analysis follows five major stages:

1. Collect reliable performance measurements for different input sizes.
2. Fit multiple mathematical models to the observed measurements.
3. Evaluate the quality of each model using statistical criteria.
4. Validate the models using log-log analysis, normalized cost, and extrapolation.
5. Compare the empirical results with theoretical complexity expectations.

### 7.1 Performance Data Collection

For each workload, measurements are collected over a range of input sizes.

Let:

- \(N\) denote the input size.
- \(C(N)\) denote the measured CPU cycles consumed by the workload.
- \(\widehat{C}(N)\) denote the cycles predicted by a fitted mathematical model.

The input sizes should cover a sufficiently large range to reveal differences between possible growth rates.

For example, a suitable sequence of input sizes could be:

\[
N = 100,\ 200,\ 400,\ 800,\ 1600,\ 3200,\ldots
\]

Geometrically increasing input sizes are useful because they make multiplicative growth easier to identify.

For each input size:

- Execute the workload multiple times.
- Use the same measurement procedure across all input sizes.
- Record the CPU cycles for every execution.
- Use the median of repeated measurements as the representative value.
- Keep the hardware, compiler, optimization flags, and execution environment consistent.

The median is preferred over a single measurement because it reduces the influence of occasional interruptions and unusually high execution times.

The measurements should be stored in a structured dataset:

| Input size \(N\) | Run 1 | Run 2 | Run 3 | Median cycles |
|---|---:|---:|---:|---:|
| \(N_1\) | ... | ... | ... | ... |
| \(N_2\) | ... | ... | ... | ... |
| \(N_3\) | ... | ... | ... | ... |

Measurements should be taken over the workload itself rather than including unrelated operations such as file input, output, or input generation, unless those operations are explicitly part of the workload being analyzed.

### 7.2 Candidate Complexity Models

Each workload is fitted against several candidate mathematical functions.

The purpose is to identify which growth function best explains the observed performance data.

Let \(C(N)\) represent the measured number of cycles.

The candidate models are:

| Model | Mathematical Form | Expected Complexity |
|---|---|---|
| Constant | \(C(N)=a\) | \(O(1)\) |
| Logarithmic | \(C(N)=a\ln N+b\) | \(O(\log N)\) |
| Linear | \(C(N)=aN+b\) | \(O(N)\) |
| Linearithmic | \(C(N)=aN\ln N+b\) | \(O(N\log N)\) |
| Quadratic | \(C(N)=aN^2+bN+c\) | \(O(N^2)\) |
| Cubic | \(C(N)=aN^3+bN^2+cN+d\) | \(O(N^3)\) |
| Exponential | \(C(N)=a2^N+b\) | \(O(2^N)\) |

Here, \(a,b,c,d\) are fitted parameters whose values are determined from the experimental measurements.

**Coefficient constraints:**

The fitted model should predict non-negative execution costs over the measured input range.

However, it is not necessary to constrain every coefficient to be non-negative. For example, a polynomial can have a positive leading coefficient and negative lower-order coefficients while still predicting positive execution costs.

The leading coefficient should be positive for the usual positive-growth models, while lower-order coefficients and constant offsets may take either sign.

This distinction is important because imposing non-negative constraints on every coefficient can unnecessarily restrict the fitting process and produce inaccurate models.

**Model fitting procedure:**

For each candidate model:

1. Substitute the measured input sizes into the mathematical expression.
2. Estimate the unknown parameters using least-squares regression.
3. Calculate the predicted execution cost for every input size.
4. Compare the predicted values with the actual measurements.
5. Store the fitted parameters and model evaluation statistics.

The primary fitting objective is to minimize the residual sum of squares:

\[
RSS=\sum_{i=1}^{m}
\left(C(N_i)-\widehat{C}(N_i)\right)^2
\]

where \(m\) is the number of measured input sizes.

All candidate models should be fitted using the same measurement dataset and the same error scale so that their statistical comparisons remain meaningful.

### 7.3 Why R-squared Alone Is Not Enough

A common approach to evaluating regression models is the coefficient of determination, \(R^2\).

It is defined as:

\[
R^2=
1-
\frac{
\sum_{i=1}^{m}(C(N_i)-\widehat{C}(N_i))^2
}{
\sum_{i=1}^{m}(C(N_i)-\overline{C})^2
}
\]

where:

\[
\overline{C}=\frac{1}{m}\sum_{i=1}^{m}C(N_i)
\]

An \(R^2\) value close to 1 indicates that the model explains a large proportion of the variation in the measured data.

However, a high \(R^2\) does not necessarily mean that the selected complexity class is correct.

For example, a quadratic model:

\[
C(N)=aN^2+bN+c
\]

can fit approximately linear data by assigning a very small value to \(a\).

Similarly, a cubic model can approximate quadratic or linear growth by making its higher-order coefficients sufficiently small.

Therefore, a more flexible model may achieve a higher \(R^2\) simply because it has more parameters.

To avoid selecting unnecessarily complicated models, we combine \(R^2\) with the following evaluation methods.

#### 7.3.1 Akaike Information Criterion (AIC)

AIC evaluates the trade-off between goodness of fit and model complexity.

For least-squares regression with approximately Gaussian residuals, an AIC score, ignoring a common additive constant, can be calculated as:

\[
\boxed{
AIC=m\ln\left(\frac{RSS}{m}\right)+2k
}
\]

where:

- \(m\) is the number of observations.
- \(RSS\) is the residual sum of squares.
- \(k\) is the number of fitted model parameters.

A model with more parameters receives a larger complexity penalty.

**Interpretation:** Lower AIC values indicate a preferable balance between fitting accuracy and model simplicity.

#### 7.3.2 Bayesian Information Criterion (BIC)

BIC is another model-selection criterion that penalizes unnecessary parameters.

It is calculated as:

\[
\boxed{
BIC=m\ln\left(\frac{RSS}{m}\right)+k\ln(m)
}
\]

Unlike AIC, the penalty increases with the logarithm of the number of observations.

As the dataset becomes larger, BIC generally applies a stronger penalty to additional parameters.

**Interpretation:** The model with the lowest BIC is preferred among the candidate models being compared.

Both AIC and BIC should be calculated using the same observations and the same response scale.

Neither criterion proves that a particular theoretical complexity class is correct. They provide evidence for selecting between the candidate models.

### 7.4 Log-Log Analysis

Log-log analysis is used to investigate polynomial growth rates.

Suppose the execution cost follows:

\[
C(N)=aN^k
\]

Taking logarithms on both sides:

\[
\ln C(N)=\ln a+k\ln N
\]

This is a linear equation of the form:

\[
y=mx+c
\]

where:

\[
y=\ln C(N),\qquad x=\ln N
\]

and the slope is:

\[
\boxed{k}
\]

Therefore, the slope of the log-log plot provides an estimate of the polynomial growth exponent.

Expected approximate slopes:

| Complexity | Expected Log-Log Slope |
|---|---:|
| \(O(1)\) | 0 |
| \(O(\log N)\) | Approaches 0 |
| \(O(N)\) | 1 |
| \(O(N\log N)\) | Approaches 1 |
| \(O(N^2)\) | 2 |
| \(O(N^3)\) | 3 |

For each workload:

1. Transform the input sizes using \(\ln N\).
2. Transform the measured cycles using \(\ln C(N)\).
3. Plot \(\ln C(N)\) against \(\ln N\).
4. Fit a straight line to the transformed data.
5. Record the estimated slope.
6. Compare the slope against the expected theoretical exponent.

The slope should preferably be estimated over the larger input sizes, where constant and lower-order terms have less influence.

**Important limitation:**

Log-log analysis alone cannot reliably distinguish \(O(N)\) from \(O(N\log N)\), because both have slopes approaching 1.

For a linearithmic workload:

\[
C(N)=aN\ln N
\]

the local log-log slope is:

\[
\frac{d\ln C(N)}{d\ln N}
=
1+\frac{1}{\ln N}
\]

which approaches 1 as \(N\) increases.

An exponential workload also does not produce a constant log-log slope. For \(C(N)=a2^N\), the local log-log slope grows with \(N\). A semi-log plot of \(\ln C(N)\) against \(N\) is a more appropriate additional diagnostic for exponential growth.

### 7.5 Normalized Cost Analysis

Normalized cost provides another way to identify the underlying growth rate.

The main idea is to divide the measured execution cost by a candidate growth function.

If the selected growth function is correct, the normalized cost should approach a constant as the input size increases.

Define:

\[
\boxed{
C_{\text{normalized}}(N)=\frac{C(N)}{f(N)}
}
\]

where \(f(N)\) is the candidate growth function.

The expected normalization functions are:

| Candidate Complexity | Normalization |
|---|---|
| \(O(1)\) | \(C(N)\) |
| \(O(\log N)\) | \(\frac{C(N)}{\ln N}\) |
| \(O(N)\) | \(\frac{C(N)}{N}\) |
| \(O(N\log N)\) | \(\frac{C(N)}{N\ln N}\) |
| \(O(N^2)\) | \(\frac{C(N)}{N^2}\) |
| \(O(N^3)\) | \(\frac{C(N)}{N^3}\) |
| \(O(2^N)\) | \(\frac{C(N)}{2^N}\) |

For example, if:

\[
C(N)=aN^2+bN+c
\]

then:

\[
\frac{C(N)}{N^2}
=
a+\frac{b}{N}+\frac{c}{N^2}
\]

As \(N\) becomes large:

\[
\boxed{
\lim_{N\to\infty}\frac{C(N)}{N^2}=a
}
\]

Thus, a quadratic workload should exhibit approximately constant normalized cost when divided by \(N^2\).

Similarly, a linear workload should flatten when divided by \(N\), while a linearithmic workload should flatten when divided by \(N\ln N\).

For every workload, normalized-cost curves should be plotted against input size for the most relevant candidate complexity classes.

The best normalization is the one that exhibits the most stable behavior over the larger input sizes, rather than merely appearing flat at a few isolated measurements.

### 7.6 Extrapolation and Predictive Validation

A model that fits the existing measurements well may still fail to predict performance at larger input sizes.

To test whether a model captures the actual growth pattern, an extrapolation experiment is performed.

The procedure is:

1. Divide the measured dataset into a training set and a validation set.
2. Use smaller input sizes for training.
3. Fit all candidate models using only the training measurements.
4. Predict the execution cost for larger input sizes.
5. Compare the predictions against the actual measured costs.
6. Calculate prediction errors for every model.

The relative prediction error is defined as:

\[
\boxed{
E(N)=
\frac{|C(N)-\widehat{C}(N)|}{C(N)}
\times100
}
\]

where \(C(N)\) is the actual measured cycle count and \(\widehat{C}(N)\) is the predicted cycle count.

A lower prediction error indicates better predictive performance.

The model should ideally be tested on multiple training/validation splits rather than relying on a single split.

For example:

- Train on the smallest 60% of input sizes and validate on the remaining 40%.
- Train on the smallest 70% and validate on the remaining 30%.
- Train on the smallest 80% and validate on the remaining 20%.

This helps determine whether the selected model continues to predict the observed growth pattern beyond the range on which it was fitted.

The extrapolation test is particularly important when distinguishing models that have similar behavior over small input sizes, such as linear and linearithmic growth.

**Note:** Extrapolation is an empirical validation technique, not a mathematical proof of asymptotic complexity. Predictions far beyond the measured range should be interpreted cautiously.

### 7.7 Sorting: Best-Case vs Worst-Case Analysis

Sorting algorithms can exhibit different performance depending on the initial arrangement of the input data.

Therefore, sorting workloads should be analyzed using multiple input distributions.

The following cases should be considered:

| Case | Input Arrangement | Purpose |
|---|---|---|
| Best case | Already sorted | Measures performance on favorable input |
| Average case | Randomly shuffled | Measures typical performance |
| Worst case | Adversarial arrangement | Measures performance on unfavorable input |

For each input size \(N\), collect the CPU cycles for all three cases.

The analysis should compare:

\[
C_{\text{best}}(N),\quad
C_{\text{average}}(N),\quad
C_{\text{worst}}(N)
\]

Plot all three measurements on the same graph.

Then fit candidate complexity models independently to each case.

This allows us to investigate:

- Whether the algorithm is sensitive to input ordering.
- Whether its best and worst cases belong to different complexity classes.
- Whether random input behaves closer to the best or worst case.
- Whether the experimental results agree with the theoretical analysis of the sorting algorithm.

For algorithms such as insertion sort, different input orders can produce substantial differences in execution cost. For algorithms such as merge sort, the asymptotic running time is generally \(O(N\log N)\) across these arrangements, although constant factors may still differ.

The input-generation procedure must be documented so that best-case, average-case, and worst-case measurements are reproducible.

### 7.8 Plots and Visualizations

The following plots will be generated for every workload to visualize and validate the measured growth patterns.

#### Plot 1: Cycles vs Input Size (Linear Axes)

- X-axis: Input size \(N\).
- Y-axis: Measured CPU cycles.
- Plot the actual measurements.
- Overlay the fitted candidate model.
- Use this plot to compare absolute execution costs and identify large deviations.

#### Plot 2: Cycles vs Input Size (Log-Log Axes)

- X-axis: \(\log N\).
- Y-axis: \(\log C(N)\).
- Include a fitted straight-line trend where appropriate.
- Display the estimated log-log slope.
- Compare the measured slope with the expected theoretical growth exponent.

#### Plot 3: Normalized Cost vs Input Size

Generate separate normalized-cost curves for the relevant candidate functions:

\[
\frac{C(N)}{N},\quad
\frac{C(N)}{N\log N},\quad
\frac{C(N)}{N^2},\quad
\frac{C(N)}{N^3}
\]

Also include the logarithmic and exponential normalizations where relevant.

The objective is to identify which normalization produces the most stable curve as \(N\) increases.

#### Plot 4: Comparison of All Workloads

- Display all workloads on a common log-log chart.
- Use consistent axis scaling.
- Include labels for each workload.
- Compare the estimated growth rates.
- Identify workloads that scale similarly and those that grow substantially faster.

If the workloads have very different absolute cycle counts, consider using separate panels or clearly documented scaling so that smaller workloads remain visible.

#### Plot 5: Sorting Best Case vs Average Case vs Worst Case

- Plot all three input arrangements on the same graph.
- Compare their measured CPU cycles.
- Overlay fitted growth models.
- Examine whether the input distribution changes the empirical growth rate or mainly changes the constant factor.

#### Plot 6: Actual vs Predicted Cycles

- X-axis: Input size \(N\).
- Y-axis: CPU cycles.
- Plot actual measured values and model predictions.
- Clearly distinguish training measurements from validation measurements.
- Use this plot to evaluate extrapolation accuracy.

### 7.9 Final Model Selection

The final complexity classification should not be determined by a single statistical score.

Instead, each candidate model should be evaluated using the combined evidence from:

1. **Goodness of fit:** Does the model closely match the measured CPU cycles?
2. **AIC and BIC:** Does the model explain the data without unnecessary parameters?
3. **Log-log slope:** Does the estimated growth exponent agree with the candidate complexity?
4. **Normalized cost:** Does dividing the measured cost by the proposed growth function produce a stable curve?
5. **Extrapolation:** Does the model predict larger input sizes accurately?
6. **Theoretical consistency:** Does the empirical result agree with the known structure of the workload?

A final comparison table should be prepared for every workload:

| Candidate Model | \(R^2\) | AIC | BIC | Log-Log Slope | Validation Error |
|---|---:|---:|---:|---:|---:|
| Constant | ... | ... | ... | ... | ... |
| Logarithmic | ... | ... | ... | ... | ... |
| Linear | ... | ... | ... | ... | ... |
| Linearithmic | ... | ... | ... | ... | ... |
| Quadratic | ... | ... | ... | ... | ... |
| Cubic | ... | ... | ... | ... | ... |
| Exponential | ... | ... | ... | ... | ... |

The final reported complexity should be the growth class that is consistently supported by the different evaluation methods.

If multiple models remain plausible, the result should explicitly mention that the available measurements are insufficient to distinguish them reliably.

The goal is not simply to find the curve with the smallest fitting error. The goal is to identify the simplest mathematically reasonable growth model that explains the measurements, predicts unseen input sizes, and agrees with the algorithm's theoretical behavior.

### 7.10 Expected Deliverables

The analysis phase should produce the following artifacts:

- [ ] Raw benchmark measurements for every workload and input size.
- [ ] Median cycle counts and measurement statistics.
- [ ] Fitted parameters for every candidate complexity model.
- [ ] \(R^2\), RSS, AIC, and BIC comparison tables.
- [ ] Log-log plots with estimated slopes.
- [ ] Normalized-cost plots for competing growth functions.
- [ ] Actual-versus-predicted performance plots.
- [ ] Extrapolation and validation error tables.
- [ ] Best-case, average-case, and worst-case sorting comparisons.
- [ ] A final complexity classification for each workload.
- [ ] A comparison between empirical and theoretical complexity.

The final report should include both the numerical results and the visualizations, together with a brief explanation of why a particular complexity class was selected.

**Final objective:** Establish a reproducible experimental methodology for determining algorithmic growth rates, rather than relying solely on theoretical assumptions or regression fit scores.
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
