# Algorithmic Execution Profiler

CS207 project. Measures how an algorithm's cost grows with input size (Big-O)
by counting exact instruction cycles on a simulated 16-bit Hack computer
(nand2tetris), instead of using noisy wall-clock time.

**Status:** work in progress

## Pipeline

Jack program → Jack compiler → VM translator → Assembler → C++ emulator (counts cycles) → Python (curve fitting and plots)

## Plan

See [docs/plan.md](docs/plan.md)
