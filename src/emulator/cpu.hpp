
// cpu.hpp
// Contract for the Hack CPU emulator.
// Declares the CPU state (A, D, PC, ROM, RAM) and the functions the rest of the
// project (main.cpp, telemetry, tests) is allowed to call. Implementation: cpu.cpp.

#pragma once
#include <cstdint> 
#include <cstddef>
#include <array>
#include <string>

// Telemetry is defined in telemetry.hpp. Forward-declared here so cpu.hpp
// stays independent and the emulator still works with telemetry turned off.
struct Telemetry;

// ---------------------------------------------------------------------------
// Hack platform constants
// ---------------------------------------------------------------------------
constexpr std::size_t ROM_SIZE      = 32768;  // 15-bit program counter

// RAM map:
//   0..16383      normal RAM
//   16384..24575  screen
//   24576         keyboard
//   24577..24579  emulator ports (NOT part of real Hack hardware)
//                   24577 = ROI START: write non-zero to start measuring
//                   24578 = ROI END:   write non-zero to stop measuring
//                   24579 = HALT:      write non-zero to stop the CPU
constexpr std::size_t RAM_SIZE      = 24580;
constexpr uint16_t    SCREEN_BASE   = 16384;
constexpr uint16_t    KBD_ADDR      = 24576;
constexpr uint16_t    PORT_ROI_START = 24577;
constexpr uint16_t    PORT_ROI_END   = 24578;

class CPU {
public:
    // -----------------------------------------------------------------------
    // Registers (public so tests and the CLI can inspect them directly)
    // -----------------------------------------------------------------------
    uint16_t A  = 0;   // address / data register
    uint16_t D  = 0;   // data register
    uint16_t PC = 0;   // program counter (15 bits used)

    // Total instructions executed. Hack does 1 instruction per cycle,
    // so this IS the cycle count used for the regression.
    uint64_t cycles = 0;

    // Halt port. Writing a non-zero value to this RAM address stops the CPU.
    // Jack programs do this with:  do Memory.poke(24579, 1);
    // Must be inside RAM (below RAM_SIZE). Set to -1 to disable.
    int32_t done_addr = 24579;

    // -----------------------------------------------------------------------
    // Setup
    // -----------------------------------------------------------------------
    CPU();

    // Attach a telemetry collector (non-owning). Pass nullptr to disable.
    void attach_telemetry(Telemetry* t) { telemetry = t; }

    // Load a .hack file (text, one 16-character binary string per line) into ROM.
    // Returns false if the file can't be opened or a line is malformed.
    bool load_rom(const std::string& hack_path);

    // Zero registers, cycle count and RAM. ROM is kept.
    void reset();

    // -----------------------------------------------------------------------
    // Execution
    // -----------------------------------------------------------------------

    // Fetch, decode and execute exactly one instruction at ROM[PC].
    // Increments `cycles`, updates PC, and may set the halted flag.
    void execute_instruction();

    // Run until halted() or max_cycles is reached. Returns cycles executed.
    // max_cycles is a safety cap against runaway programs.
    uint64_t run(uint64_t max_cycles = 1'000'000'000ULL);

    // True when the program is finished. This happens when:
    //   - the program wrote a non-zero value to the halt port (done_addr), or
    //   - PC ran past the loaded program, or
    //   - the program hit the hand-written halt idiom  (@X  /  0;JMP  jumping to itself).
    // If run() returns and halted() is false, the cycle cap was hit instead.
    bool halted() const { return is_halted; }

    // Region of interest (ROI). A program marks the part of its run worth measuring
    // by writing a non-zero value to PORT_ROI_START just before it and to PORT_ROI_END
    // just after it. The telemetry counters are zeroed at the start write and frozen
    // at the end write, so start-up code and anything after the end is not counted.
    // The end-write instruction itself IS counted; the start-write instruction is not.
    // If a program never uses the ports, telemetry counts the whole run (as before).
    bool roi_started() const { return roi_seen_start; }
    bool roi_ended()   const { return roi_seen_end; }

    // -----------------------------------------------------------------------
    // Memory access for the host (CLI, tests). NOT counted as telemetry.
    // Used by --ram-init to preload N and the data array, and to read results.
    // -----------------------------------------------------------------------
    void    poke(uint16_t addr, int16_t value);
    int16_t peek(uint16_t addr) const;

    std::size_t program_size() const { return rom_size; }

private:
    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------
    std::array<uint16_t, ROM_SIZE> rom{};
    std::array<int16_t,  RAM_SIZE> ram{};
    std::size_t rom_size  = 0;       // number of instructions loaded
    bool        is_halted = false;
    Telemetry*  telemetry = nullptr; // optional, non-owning
    bool        roi_seen_start = false;  // program wrote the ROI-start port
    bool        roi_seen_end   = false;  // program wrote the ROI-end port
    bool        counting       = true;   // telemetry counts only while this is true

    // -----------------------------------------------------------------------
    // Instruction handlers
    // -----------------------------------------------------------------------

    // A-instruction  (0vvvvvvvvvvvvvvv): A = 15-bit value.
    void execute_a_instruction(uint16_t instr);

    // C-instruction  (111accccccdddjjj): compute, store to dest, maybe jump.
    // Note: if dest includes M, it writes RAM[A] using the OLD value of A,
    // even if dest also includes A (hardware writes all dests in the same cycle).
    void execute_c_instruction(uint16_t instr);

    // ALU: `comp` is the 7-bit a+c1..c6 field. x = D, y = A or M (chosen by the a-bit).
    int16_t alu(uint8_t comp, int16_t x, int16_t y) const;

    // True if the 3-bit jump field is satisfied by the ALU output.
    static bool should_jump(uint8_t jump, int16_t alu_out);

    // -----------------------------------------------------------------------
    // Memory accessors used DURING execution (these feed telemetry hooks)
    // -----------------------------------------------------------------------
    int16_t read_mem(uint16_t addr);
    void    write_mem(uint16_t addr, int16_t value);

    // -----------------------------------------------------------------------
    // Bit-field decoding helpers
    // -----------------------------------------------------------------------
    static constexpr bool    is_c_instruction(uint16_t i) { return (i & 0x8000) != 0; }
    static constexpr uint8_t comp_bits(uint16_t i)        { return (i >> 6) & 0x7F; } // a + c1..c6
    static constexpr uint8_t dest_bits(uint16_t i)        { return (i >> 3) & 0x07; } // A, D, M
    static constexpr uint8_t jump_bits(uint16_t i)        { return  i       & 0x07; } // JGT, JEQ, JLT
};
