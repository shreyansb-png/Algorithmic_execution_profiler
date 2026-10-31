// cpu.cpp
// Hack CPU: fetch-decode-execute, ALU, and memory updates.

#include "cpu.hpp"
#include "telemetry.hpp" 

#include <algorithm>
#include <cctype> 
#include <fstream>

CPU::CPU(){}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

bool CPU::load_rom(const std::string& hack_path) {
    std::ifstream in(hack_path);
    if (!in) return false;

    std::fill(rom.begin(), rom.end(), 0);
    rom_size = 0;

    std::string line;
    while (std::getline(in, line)) {
        // Trim trailing whitespace (handles Windows \r\n line endings).
        while (!line.empty() && std::isspace(static_cast<unsigned char>(line.back())))
            line.pop_back();
        if (line.empty()) continue;

        if (line.size() != 16 || rom_size >= ROM_SIZE) return false;

        uint16_t word = 0;
        for (char c : line) {
            if (c != '0' && c != '1') return false;
            word = static_cast<uint16_t>((word << 1) | (c - '0'));
        }
        rom[rom_size++] = word;
    }

    PC = 0;
    cycles = 0;
    is_halted = false;
    return rom_size > 0;
}

void CPU::reset() {
    A = D = PC = 0;
    cycles = 0;
    is_halted = false;
    ram.fill(0);
    if (telemetry) telemetry->reset();
}

// ---------------------------------------------------------------------------
// Execution
// ---------------------------------------------------------------------------

void CPU::execute_instruction() {
    if (PC >= rom_size) {          // ran off the end of the program
        is_halted = true;
        return;
    }

    const uint16_t instr = rom[PC];

    ++cycles;
    if (telemetry) ++telemetry->cycles;

    if (is_c_instruction(instr)) execute_c_instruction(instr);
    else                         execute_a_instruction(instr);
}

uint64_t CPU::run(uint64_t max_cycles) {
    const uint64_t start = cycles;
    while (!is_halted && (cycles - start) < max_cycles) {
        execute_instruction();
    }
    return cycles - start;
}

void CPU::execute_a_instruction(uint16_t instr) {
    A = instr & 0x7FFF;
    ++PC;
}

void CPU::execute_c_instruction(uint16_t instr) {
    const uint8_t comp = comp_bits(instr);
    const uint8_t dest = dest_bits(instr);
    const uint8_t jump = jump_bits(instr);

    // Snapshot A: hardware uses this value for the whole cycle.
    const uint16_t old_A = A;

    // ---- Compute -----------------------------------------------------------
    const int16_t x = static_cast<int16_t>(D);
    const int16_t y = (comp & 0x40)                       // a-bit: 1 => use M
                          ? read_mem(old_A)
                          : static_cast<int16_t>(old_A);
    const int16_t out = alu(comp, x, y);

    // ---- Store -------------------------------------------------------------
    if (dest & 0x01) write_mem(old_A, out);               // M  (uses OLD A)
    if (dest & 0x02) D = static_cast<uint16_t>(out);
    if (dest & 0x04) A = static_cast<uint16_t>(out);

    // ---- Jump --------------------------------------------------------------
    if (jump != 0 && should_jump(jump, out)) {
        const uint16_t target = old_A & 0x7FFF;

        // Halt idiom: unconditional jump with no side effects that lands on
        // itself (@X where X == this JMP) or on the @X right before it.
        if (jump == 7 && dest == 0 &&
            (target == PC || (target + 1 == PC && rom[target] == target))) {
            is_halted = true;
        }
        PC = target;
    } else {
        ++PC;
    }
}

// ---------------------------------------------------------------------------
// ALU
// ---------------------------------------------------------------------------

int16_t CPU::alu(uint8_t comp, int16_t x, int16_t y) const {
    switch (comp & 0x3F) {                 // c1..c6; the a-bit was handled by the caller
        case 0b101010: return 0;
        case 0b111111: return 1;
        case 0b111010: return -1;
        case 0b001100: return x;
        case 0b110000: return y;
        case 0b001101: return static_cast<int16_t>(~x);
        case 0b110001: return static_cast<int16_t>(~y);
        case 0b001111: return static_cast<int16_t>(-x);
        case 0b110011: return static_cast<int16_t>(-y);
        case 0b011111: return static_cast<int16_t>(x + 1);
        case 0b110111: return static_cast<int16_t>(y + 1);
        case 0b001110: return static_cast<int16_t>(x - 1);
        case 0b110010: return static_cast<int16_t>(y - 1);
        case 0b000010: return static_cast<int16_t>(x + y);
        case 0b010011: return static_cast<int16_t>(x - y);
        case 0b000111: return static_cast<int16_t>(y - x);
        case 0b000000: return static_cast<int16_t>(x & y);
        case 0b010101: return static_cast<int16_t>(x | y);
        default:       return 0;           // not a valid Hack comp code
    }
}

bool CPU::should_jump(uint8_t jump, int16_t out) {
    return ((jump & 4) && out <  0) ||     // j1: JLT
           ((jump & 2) && out == 0) ||     // j2: JEQ
           ((jump & 1) && out >  0);       // j3: JGT
}

// ---------------------------------------------------------------------------
// Memory
// ---------------------------------------------------------------------------

int16_t CPU::read_mem(uint16_t addr) {
    if (telemetry) ++telemetry->ram_reads;
    return addr < RAM_SIZE ? ram[addr] : 0;   // out-of-range reads give 0
}

void CPU::write_mem(uint16_t addr, int16_t value) {
    if (telemetry) ++telemetry->ram_writes;
    if (addr < RAM_SIZE) {                    // out-of-range writes are ignored
        ram[addr] = value;
        if (static_cast<int32_t>(addr) == done_addr && value != 0) is_halted = true;
    }
}

void CPU::poke(uint16_t addr, int16_t value) {
    if (addr < RAM_SIZE) ram[addr] = value;
}

int16_t CPU::peek(uint16_t addr) const {
    return addr < RAM_SIZE ? ram[addr] : 0;
}
