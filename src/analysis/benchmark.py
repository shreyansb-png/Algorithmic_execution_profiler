import csv
import re
import shutil
import subprocess
import statistics

from datetime import datetime, timezone
from pathlib import Path


# =====================================================
# 1. PROJECT PATHS
# =====================================================

ROOT = Path(r"C:\n2t-work")

ANALYSIS_DIR = ROOT / "analysis"

SOURCE_HELLO_DIR = ROOT / "hello"

EMU_DIR = ROOT / "emu"

PROFILER_EXE = EMU_DIR / "profiler.exe"

VM_TRANSLATOR_EXE = (
    ROOT / "VMtranslator" / "VMTranslator.exe"
)

# This is the tools path that worked in your setup.
# Change it only if your installation is elsewhere.

TOOLS_DIR = Path(
    r"C:\Users\shreyans\Downloads\nand2tetris\nand2tetris\tools"
)

JACK_COMPILER_BAT = TOOLS_DIR / "JackCompiler.bat"

ASSEMBLER_BAT = TOOLS_DIR / "Assembler.bat"


# =====================================================
# 2. WORKLOAD AND OUTPUT DIRECTORIES
# =====================================================

WORKLOADS_DIR = ANALYSIS_DIR / "workloads"

BUILD_ROOT = ANALYSIS_DIR / "build"

DATA_DIR = ANALYSIS_DIR / "data"

CSV_FILE = DATA_DIR / "benchmarks.csv"


# =====================================================
# 3. EXPERIMENT CONFIGURATION
# =====================================================

# The same input sizes are used for every workload.
# This makes the comparison easier to interpret.

N_VALUES = [8, 16,32,64,128,256,512]

RUNS_PER_N = 3

PEEK_ADDRESS = 16384

# Your current emulator output:
# 0,2694,1023,566
#
# We currently assume the second field contains
# the ROI cycle count.

ROI_CYCLE_FIELD_INDEX = 1

TIMEOUT_SECONDS = 180


# =====================================================
# 4. UTILITY FUNCTIONS
# =====================================================

def fail(message):

    raise RuntimeError(message)


def check_file(path):

    if not path.exists():

        fail(f"File not found: {path}")


def run_batch(batch_file, argument, cwd):

    check_file(batch_file)

    command = (
        f'call "{batch_file.resolve()}" '
        f'"{Path(argument).resolve()}"'
    )

    result = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS
    )

    output = (
        (result.stdout or "")
        + "\n"
        + (result.stderr or "")
    )

    if result.returncode != 0:

        fail(
            f"Batch command failed:\n"
            f"{command}\n\n{output}"
        )

    return output


def run_executable(exe, args, cwd):

    check_file(exe)

    command = [
        str(exe.resolve())
    ] + [
        str(Path(x).resolve())
        if isinstance(x, Path)
        else str(x)
        for x in args
    ]

    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS
    )

    output = (
        (result.stdout or "")
        + "\n"
        + (result.stderr or "")
    )

    if result.returncode != 0:

        fail(
            f"Executable failed:\n"
            f"{command}\n\n{output}"
        )

    return output


# =====================================================
# 5. DISCOVER WORKLOADS AUTOMATICALLY
# =====================================================
def discover_workloads():

    check_file(WORKLOADS_DIR)

    templates = sorted(
        WORKLOADS_DIR.glob("*.template")
    )

    if not templates:
        fail(
            "No workload templates found inside:\n"
            + str(WORKLOADS_DIR)
        )

    discovered = []

    names = set()

    for template in templates:

        name = template.stem

        if name in names:
            fail(
                f"Duplicate workload name: {name}"
            )

        names.add(name)

        source = template.read_text(
            encoding="utf-8"
        )

        if "N_VALUE" not in source:
            fail(
                f"{template.name} must contain "
                "at least one N_VALUE placeholder."
            )

        if "class Main" not in source:
            fail(
                f"{template.name} must contain "
                "class Main."
            )

        discovered.append(template)

    return discovered



# =====================================================
# 6. VALIDATE CONFIGURATION
# =====================================================

def validate_configuration():

    required = [
        SOURCE_HELLO_DIR,
        PROFILER_EXE,
        VM_TRANSLATOR_EXE,
        JACK_COMPILER_BAT,
        ASSEMBLER_BAT,
        WORKLOADS_DIR
    ]

    for path in required:

        check_file(path)

    if not (
        SOURCE_HELLO_DIR / "Sys.jack"
    ).exists():

        fail("Sys.jack is missing from hello.")

    for vm_file in [
        "Array.vm",
        "Math.vm",
        "Memory.vm"
    ]:

        if not (
            SOURCE_HELLO_DIR / vm_file
        ).exists():

            fail(
                f"Required OS VM file missing: {vm_file}"
            )

    if not N_VALUES:

        fail("N_VALUES cannot be empty.")

    for n in N_VALUES:

        if n <= 0 or n >= 32767:

            fail(
                f"Invalid N={n}. "
                "Use positive values below 32767."
            )

    if RUNS_PER_N <= 0:

        fail("RUNS_PER_N must be positive.")


# =====================================================
# 7. BACKUP PREVIOUS EXPERIMENT
# =====================================================

def backup_previous_csv():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if CSV_FILE.exists():

        timestamp = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d_%H%M%S")

        backup = DATA_DIR / (
            f"benchmarks_previous_{timestamp}.csv"
        )

        shutil.move(
            str(CSV_FILE),
            str(backup)
        )

        print(
            "Previous CSV backed up to:",
            backup
        )


# =====================================================
# 8. GENERATE JACK SOURCE
# =====================================================

def prepare_build(template, workload, n):

    workload_root = (
        BUILD_ROOT / workload
    )

    if workload_root.exists():

        shutil.rmtree(workload_root)

    hello_dir = workload_root / "hello"

    hello_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # Copy the original hello folder.
    # This preserves Sys.jack and OS VM files.

    shutil.copytree(
        SOURCE_HELLO_DIR,
        hello_dir,
        dirs_exist_ok=True
    )

    # Read the selected template.

    source = template.read_text(
        encoding="utf-8"
    )

    # Replace N_VALUE.

    generated = source.replace(
        "N_VALUE",
        str(n)
    )

    # Write temporary Main.jack.

    main_file = hello_dir / "Main.jack"

    main_file.write_text(
        generated,
        encoding="utf-8"
    )

    return hello_dir


# =====================================================
# 9. JACK -> VM
# =====================================================

def compile_jack(hello_dir):

    print("Compiling Jack...")

    output = run_batch(
        JACK_COMPILER_BAT,
        hello_dir,
        TOOLS_DIR
    )

    main_vm = hello_dir / "Main.vm"

    if not main_vm.exists():

        fail(
            "Jack compiler did not generate Main.vm.\n"
            + output
        )

    print("Jack compilation successful.")

    return output


# =====================================================
# 10. VM -> ASM
# =====================================================

def translate_vm(hello_dir):

    print("Running VMTranslator...")

    output = run_executable(
        VM_TRANSLATOR_EXE,
        [hello_dir],
        BUILD_ROOT
    )

    candidates = set()

    for folder in [
        hello_dir,
        hello_dir.parent
    ]:

        for file in folder.glob("*.asm"):

            candidates.add(file)

    candidates = sorted(candidates)

    if len(candidates) == 0:

        fail(
            "VMTranslator did not generate an ASM file.\n"
            + output
        )

    if len(candidates) > 1:

        fail(
            "Multiple ASM files found:\n"
            + "\n".join(
                str(x) for x in candidates
            )
        )

    asm_file = candidates[0]

    print("ASM generated:", asm_file)

    return asm_file


# =====================================================
# 11. ASM -> HACK
# =====================================================

def assemble(asm_file):

    print("Running Assembler...")

    output = run_batch(
        ASSEMBLER_BAT,
        asm_file,
        TOOLS_DIR
    )

    hack_file = asm_file.with_suffix(".hack")

    if not hack_file.exists():

        fail(
            "Assembler did not generate HACK file.\n"
            + output
        )

    print("HACK generated:", hack_file)

    return hack_file


# =====================================================
# 12. RUN CPU EMULATOR
# =====================================================

def run_emulator(hack_file):

    print("Running CPU emulator...")

    output = run_executable(
        PROFILER_EXE,
        [
            hack_file,
            "--peek",
            str(PEEK_ADDRESS)
        ],
        EMU_DIR
    )

    return output


# =====================================================
# 13. EXTRACT MEASUREMENTS
# =====================================================

def parse_output(output):

    # ROI must have been activated.

    if not re.search(
        r"region of interest used",
        output,
        re.IGNORECASE
    ):

        fail(
            "ROI was not detected.\n"
            + output
        )

    # Read correctness flag.

    ram_pattern = (
        rf"RAM\[\s*{PEEK_ADDRESS}\s*\]"
        rf"\s*=\s*(-?\d+)"
    )

    ram_match = re.search(
        ram_pattern,
        output
    )

    if not ram_match:

        fail(
            "Could not find RAM verification value.\n"
            + output
        )

    ram_value = int(
        ram_match.group(1)
    )

    if ram_value != 1:

        fail(
            f"Incorrect workload result. "
            f"Expected RAM={PEEK_ADDRESS} to be 1, "
            f"got {ram_value}."
        )

    # Read whole execution cycles.

    whole_match = re.search(
        r"whole run was\s+([\d,]+)\s+cycles",
        output,
        re.IGNORECASE
    )

    whole_cycles = None

    if whole_match:

        whole_cycles = int(
            whole_match.group(1).replace(",", "")
        )

    # Extract comma-separated ROI line.

    csv_lines = []

    for line in output.splitlines():

        line = line.strip()

        if re.fullmatch(
            r"-?\d+(?:\s*,\s*-?\d+)+",
            line
        ):

            csv_lines.append(line)

    if not csv_lines:

        fail(
            "Could not find ROI CSV line.\n"
            + output
        )

    roi_line = csv_lines[-1]

    roi_values = [
        int(x.strip())
        for x in roi_line.split(",")
    ]

    if (
        ROI_CYCLE_FIELD_INDEX
        >= len(roi_values)
    ):

        fail(
            "Invalid ROI cycle field index.\n"
            + roi_line
        )

    roi_cycles = roi_values[
        ROI_CYCLE_FIELD_INDEX
    ]

    if roi_cycles <= 0:

        fail("ROI cycle count must be positive.")

    return {

        "roi_cycles": roi_cycles,

        "roi_line": roi_line,

        "roi_values": roi_values,

        "whole_cycles": whole_cycles,

        "ram_value": ram_value,

        "correct": True
    }


# =====================================================
# 14. SAVE MEASUREMENT
# =====================================================

CSV_FIELDS = [

    "timestamp_utc",

    "workload",

    "N",

    "run",

    "roi_cycles",

    "roi_line",

    "roi_field_0",

    "roi_field_1",

    "roi_field_2",

    "roi_field_3",

    "whole_cycles",

    "ram_16384",

    "correct"
]


def save_measurement(
    workload,
    n,
    run_number,
    data
):

    row = {

        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "workload": workload,

        "N": n,

        "run": run_number,

        "roi_cycles": data["roi_cycles"],

        "roi_line": data["roi_line"],

        "whole_cycles": data["whole_cycles"],

        "ram_16384": data["ram_value"],

        "correct": data["correct"]
    }

    for i in range(4):

        if i < len(data["roi_values"]):

            row[f"roi_field_{i}"] = (
                data["roi_values"][i]
            )

        else:

            row[f"roi_field_{i}"] = ""

    file_exists = CSV_FILE.exists()

    with CSV_FILE.open(
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=CSV_FIELDS
        )

        if not file_exists:

            writer.writeheader()

        writer.writerow(row)


# =====================================================
# 15. MAIN AUTOMATIC BENCHMARK ENGINE
# =====================================================

def main():

    print("=" * 60)

    print("AUTOMATIC ALGORITHMIC EXECUTION PROFILER")

    print("=" * 60)

    validate_configuration()

    # Discover every workload automatically.

    templates = discover_workloads()

    print("\nDiscovered workloads:")

    for template in templates:

        print("  -", template.stem)

    print("\nInput sizes:", N_VALUES)

    print("Runs per N:", RUNS_PER_N)

    print(
        "Total expected measurements:",
        len(templates)
        * len(N_VALUES)
        * RUNS_PER_N
    )

    # Start a clean experiment while preserving
    # the previous CSV as a backup.

    backup_previous_csv()

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # Loop over every discovered template.

    for template in templates:

        workload = template.stem

        print("\n" + "=" * 60)

        print("WORKLOAD:", workload)

        print("=" * 60)

        for n in N_VALUES:

            print(f"\nPreparing N = {n}")

            hello_dir = prepare_build(
                template,
                workload,
                n
            )

            compile_jack(hello_dir)

            asm_file = translate_vm(
                hello_dir
            )

            hack_file = assemble(
                asm_file
            )

            print(
                f"\nBenchmarking {workload}, N={n}"
            )

            cycle_results = []

            for run_number in range(
                1,
                RUNS_PER_N + 1
            ):

                print(
                    f"Run {run_number}/{RUNS_PER_N}"
                )

                output = run_emulator(
                    hack_file
                )

                data = parse_output(output)

                save_measurement(
                    workload,
                    n,
                    run_number,
                    data
                )

                cycle_results.append(
                    data["roi_cycles"]
                )

                print(
                    "ROI:",
                    data["roi_line"]
                )

                print(
                    "Selected cycles:",
                    data["roi_cycles"]
                )

                print(
                    "RAM correctness:",
                    data["ram_value"]
                )

            median_cycles = statistics.median(
                cycle_results
            )

            print(
                f"Median for {workload}, N={n}: "
                f"{median_cycles}"
            )

    print("\n" + "=" * 60)

    print("ALL BENCHMARKS COMPLETED")

    print("CSV:", CSV_FILE)

    print("=" * 60)


# =====================================================
# 16. ENTRY POINT
# =====================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print("\nBENCHMARK ERROR:")

        print(error)

        raise SystemExit(1)
