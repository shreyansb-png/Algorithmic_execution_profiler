
// main.cpp
// Orchestrator for the Hack emulator. Loads ROM, preloads RAM, runs execution, and outputs telemetry.
//
// Usage:
//   profiler <program.hack> [--ram-init <file.txt>] [--peek <addr>]...
//
//   --peek <addr>   after the run, print RAM[addr] to the error stream (stderr).
//                   Can be given several times. Used to check a program's answer.

#include "cpu.hpp"
#include "telemetry.hpp"

#include <iostream>
#include <fstream>
#include <string>
#include <vector>

int main(int argc, char* argv[]) {
    // 1. Parse CLI arguments
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0]
                  << " <program.hack> [--ram-init <file.txt>] [--peek <addr>]...\n";
        return 1;
    }

    std::string hack_path = argv[1];
    std::string ram_init_path = "";
    std::vector<uint16_t> peek_addrs;

    for (int i = 2; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--ram-init" && i + 1 < argc) {
            ram_init_path = argv[++i];
        } else if (arg == "--peek" && i + 1 < argc) {
            try {
                int addr = std::stoi(argv[++i]);
                if (addr < 0 || addr >= static_cast<int>(RAM_SIZE)) {
                    std::cerr << "Error: --peek address out of range (0.."
                              << RAM_SIZE - 1 << "): " << addr << "\n";
                    return 1;
                }
                peek_addrs.push_back(static_cast<uint16_t>(addr));
            } catch (...) {
                std::cerr << "Error: --peek needs a number, got: " << argv[i] << "\n";
                return 1;
            }
        }
    }

    // 2. Initialize CPU and load the compiled Jack program
    CPU cpu;
    if (!cpu.load_rom(hack_path)) {
        std::cerr << "Error: Failed to load or parse .hack ROM file: " << hack_path << "\n";
        return 1;
    }

    // 3. Preload RAM with input data (N and the array)
    int32_t N = 0;
    if (!ram_init_path.empty()) {
        std::ifstream ram_in(ram_init_path);
        if (!ram_in) {
            std::cerr << "Error: Could not open --ram-init file: " << ram_init_path << "\n";
            return 1;
        }
        
        // Expects format: <RAM_ADDRESS> <VALUE> per line
        // Example: "8000 100" (Puts N=100 at RAM[8000])
        uint16_t addr;
        int16_t value;
        bool is_first = true;
        
        while (ram_in >> addr >> value) {
            cpu.poke(addr, value);
            if (is_first) {
                N = value; // Assumes the very first loaded value represents N for the CSV
                is_first = false;
            }
        }
    }

    // 4. Attach telemetry and execute
    Telemetry telemetry;
    cpu.attach_telemetry(&telemetry);

    // Run with a 1-billion cycle safety limit to prevent infinite loops from hanging the benchmarker
    cpu.run(1'000'000'000ULL); 

    // Print any requested RAM values (to stderr, so the CSV line on stdout stays clean).
    for (uint16_t addr : peek_addrs) {
        std::cerr << "RAM[" << addr << "] = " << cpu.peek(addr) << "\n";
    }

    // If the program never halted, the run hit the cycle cap. That measurement
    // is meaningless, so report an error (exit code 2) instead of printing a
    // normal-looking CSV row that would silently ruin the regression.
    if (!cpu.halted()) {
        std::cerr << "Error: hit the cycle limit without halting\n";
        return 2;
    }

    // Region-of-interest sanity messages (stderr, so the CSV line stays clean).
    if (cpu.roi_started() && !cpu.roi_ended()) {
        std::cerr << "Warning: ROI start was written but ROI end never was; "
                     "counts run to the end of the program.\n";
    }
    if (cpu.roi_started()) {
        std::cerr << "Note: region of interest used. The whole run was "
                  << cpu.cycles << " cycles; the CSV line counts only the region.\n";
    }

    // 5. Output standard CSV format for the Python regression script
    // Format: N,cycles,reads,writes
    std::cout << N << "," 
              << telemetry.cycles << "," 
              << telemetry.ram_reads << "," 
              << telemetry.ram_writes << "\n";

    return 0;
}
