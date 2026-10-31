// telemetry.hpp
// Plain counters filled in by the CPU while it runs.
// Kept as bare integers (no maps, no virtuals) so counting costs ~nothing.

#pragma once

#include <cstdint>

struct Telemetry {
    uint64_t cycles     = 0;  // instructions executed (Hack: 1 instruction = 1 cycle)
    uint64_t ram_reads  = 0;  // reads of M (RAM[A]) as an ALU operand
    uint64_t ram_writes = 0;  // writes to M (RAM[A]) from a dest field

    void reset() { *this = Telemetry{}; }
};
