import csv
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


# =====================================================
# 1. PATHS AND OUTPUT DIRECTORIES
# =====================================================

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "benchmarks.csv"
RESULTS_DIR = ROOT / "results"
PLOTS_DIR = RESULTS_DIR / "plots"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================
# 2. CANDIDATE COMPLEXITY LABELS
# =====================================================

COMPLEXITY_NAMES = {
    "constant": "O(1)",
    "logarithmic": "O(log N)",
    "linear": "O(N)",
    "linearithmic": "O(N log N)",
    "quadratic": "O(N^2)",
    "cubic": "O(N^3)",
    "exponential": "O(2^N)",
}


# =====================================================
# 3. LOAD CSV AND GROUP BY WORKLOAD AND N
# =====================================================

def load_data():

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"CSV not found: {DATA_FILE}"
        )

    # workload -> N -> list of cycle measurements
    grouped = defaultdict(
        lambda: defaultdict(list)
    )

    with DATA_FILE.open(
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        required = {
            "workload",
            "N",
            "roi_cycles",
            "correct"
        }

        if not required.issubset(
            set(reader.fieldnames or [])
        ):
            missing = required - set(reader.fieldnames or [])
            raise ValueError(
                f"CSV is missing required columns: {sorted(missing)}"
            )

        for line_number, row in enumerate(reader, start=2):

            workload = (
                row.get("workload") or ""
            ).strip()

            if not workload:
                raise ValueError(
                    f"Missing workload name at CSV line {line_number}."
                )

            correct_value = (
                row.get("correct") or ""
            ).strip().lower()

            if correct_value not in {
                "true", "1", "yes"
            }:
                raise ValueError(
                    f"Incorrect or missing correctness flag "
                    f"at CSV line {line_number}: {row}"
                )

            try:
                n = int(row["N"])
                cycles = float(row["roi_cycles"])

            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid N or roi_cycles at CSV "
                    f"line {line_number}: {row}"
                ) from error

            if n <= 0:
                raise ValueError(
                    f"N must be positive at CSV line {line_number}."
                )

            if not math.isfinite(cycles) or cycles <= 0:
                raise ValueError(
                    f"ROI cycles must be finite and positive "
                    f"at CSV line {line_number}."
                )

            grouped[workload][n].append(cycles)

    data = {}

    for workload, by_n in grouped.items():

        input_sizes = sorted(by_n)

        medians = [
            float(np.median(by_n[n]))
            for n in input_sizes
        ]

        data[workload] = {

            "N": np.asarray(
                input_sizes,
                dtype=float
            ),

            "cycles": np.asarray(
                medians,
                dtype=float
            ),

            "runs": sum(
                len(by_n[n])
                for n in input_sizes
            )
        }

    if not data:
        raise ValueError(
            "No valid benchmark measurements were found in the CSV."
        )

    return data


# =====================================================
# 4. BUILD CANDIDATE MODEL MATRICES
# =====================================================

def get_models(N):

    """
    Build design matrices for the seven candidate models.

    The features are scaled for numerical stability.

    The returned coefficients therefore correspond to
    the scaled basis, not directly to the unscaled
    coefficients a, b, c and d.
    """

    N = np.asarray(N, dtype=float)

    if np.any(N <= 0):
        raise ValueError(
            "All input sizes must be positive."
        )

    maximum = float(np.max(N))

    x = N / maximum

    log_n = np.log(N)

    linearithmic = x * log_n

    linearithmic /= np.max(linearithmic)

    # Scaled exponential:
    # 2^(N - maximum)
    #
    # This avoids overflow for the largest N.
    # Rank checks below handle underflow or degeneracy.

    with np.errstate(
        under="ignore",
        over="ignore"
    ):
        exponential = np.exp2(
            N - maximum
        )

    one = np.ones(
        len(N),
        dtype=float
    )

    models = {

        "constant": np.column_stack([
            one
        ]),

        "logarithmic": np.column_stack([
            log_n,
            one
        ]),

        "linear": np.column_stack([
            x,
            one
        ]),

        "linearithmic": np.column_stack([
            linearithmic,
            one
        ]),

        "quadratic": np.column_stack([
            x**2,
            x,
            one
        ]),

        "cubic": np.column_stack([
            x**3,
            x**2,
            x,
            one
        ]),

        "exponential": np.column_stack([
            exponential,
            one
        ])
    }

    return models


# =====================================================
# 5. FIT ONE MODEL USING LEAST SQUARES
# =====================================================

def fit_model(X, y):

    y = np.asarray(y, dtype=float)

    parameter_count = X.shape[1]

    coefficients, _, rank, _ = np.linalg.lstsq(
        X,
        y,
        rcond=None
    )

    predictions = X @ coefficients

    residuals = y - predictions

    rss = float(
        np.sum(residuals**2)
    )

    tss = float(
        np.sum((y - np.mean(y))**2)
    )

    if tss > 0:
        r2 = 1.0 - rss / tss
    else:
        r2 = float("nan")

    # Reject rank-deficient models, models with
    # a non-positive leading coefficient, or models
    # producing non-positive predictions.

    valid = (
        rank == parameter_count
        and len(coefficients) > 0
        and coefficients[0] > 0
        and np.all(np.isfinite(predictions))
        and np.all(predictions > 0)
    )

    if not valid:

        return {

            "valid": False,

            "coefficients": coefficients,

            "predictions": predictions,

            "rss": rss,

            "r2": r2,

            "aic": float("inf"),

            "aicc": float("inf"),

            "bic": float("inf"),

            "parameters": parameter_count
        }

    n = len(y)

    # Include regression coefficients and
    # estimated residual variance in k.

    k = parameter_count + 1

    # Numerical floor prevents floating-point
    # round-off from producing artificially
    # perfect information-criterion scores.

    rss_floor = (
        np.finfo(float).eps
        * max(float(np.sum(y**2)), 1.0)
    )

    rss_for_ic = max(
        rss,
        rss_floor
    )

    aic = (
        n * np.log(rss_for_ic / n)
        + 2 * k
    )

    bic = (
        n * np.log(rss_for_ic / n)
        + k * np.log(n)
    )

    # Corrected AIC for small samples.

    if n > k + 1:

        aicc = (
            aic
            + (2 * k * (k + 1))
            / (n - k - 1)
        )

    else:

        aicc = float("inf")

    return {

        "valid": True,

        "coefficients": coefficients,

        "predictions": predictions,

        "rss": rss,

        "r2": r2,

        "aic": float(aic),

        "aicc": float(aicc),

        "bic": float(bic),

        "parameters": parameter_count
    }


# =====================================================
# 6. EXTRAPOLATION VALIDATION
# =====================================================

def validation_error(X, y):

    """
    Fit on smaller N values and predict the
    largest input sizes.

    Returns Mean Absolute Percentage Error.
    """

    n = len(y)

    if n < 6:
        return float("nan")

    train_count = max(
        4,
        int(math.ceil(0.70 * n))
    )

    train_count = min(
        train_count,
        n - 2
    )

    X_train = X[:train_count]

    y_train = y[:train_count]

    X_test = X[train_count:]

    y_test = y[train_count:]

    coefficients, _, rank, _ = np.linalg.lstsq(
        X_train,
        y_train,
        rcond=None
    )

    if rank < X_train.shape[1]:
        return float("inf")

    predictions = X_test @ coefficients

    if (
        not np.all(np.isfinite(predictions))
        or np.any(predictions <= 0)
    ):
        return float("inf")

    denominator = np.maximum(
        np.abs(y_test),
        1e-12
    )

    errors = (
        np.abs(y_test - predictions)
        / denominator
    )

    return float(
        np.mean(errors) * 100
    )


# =====================================================
# 7. LOG-LOG REGRESSION
# =====================================================

def calculate_loglog_slope(N, cycles):

    """
    Fit:

        log(C) = intercept + slope * log(N)
    """

    x = np.log(N)

    y = np.log(cycles)

    slope, intercept = np.polyfit(
        x,
        y,
        1
    )

    predictions = (
        slope * x + intercept
    )

    ss_res = float(
        np.sum((y - predictions)**2)
    )

    ss_tot = float(
        np.sum((y - np.mean(y))**2)
    )

    if ss_tot > 0:

        r2 = 1.0 - ss_res / ss_tot

    else:

        r2 = float("nan")

    return float(slope), float(r2)


# =====================================================
# 8. MODEL SELECTION
# =====================================================

def select_model(results, number_of_points):

    valid_models = {

        name: result

        for name, result in results.items()

        if result["valid"]
        and np.isfinite(result["bic"])
    }

    if not valid_models:

        return {

            "selected": "none",

            "classification": (
                "Inconclusive: no valid candidate model"
            ),

            "bic_delta": float("nan"),

            "validation_error": float("nan")
        }

    ordered = sorted(
        valid_models,
        key=lambda name: (
            valid_models[name]["bic"],
            valid_models[name]["parameters"]
        )
    )

    minimum_bic = valid_models[
        ordered[0]
    ]["bic"]

    # Models within two BIC units are difficult
    # to distinguish. Prefer the simpler model
    # for the reported candidate.

    close_models = [

        name

        for name in ordered

        if (
            valid_models[name]["bic"]
            - minimum_bic
        ) < 2.0
    ]

    best = min(
        close_models,
        key=lambda name: (
            valid_models[name]["parameters"],
            valid_models[name]["bic"]
        )
    )

    if len(ordered) > 1:

        second_bic = valid_models[
            ordered[1]
        ]["bic"]

        delta = float(
            second_bic - minimum_bic
        )

    else:

        delta = float("inf")

    complexity = COMPLEXITY_NAMES[best]

    best_validation_error = valid_models[
        best
    ]["validation_error"]

    if number_of_points < 6:

        classification = (
            "Inconclusive: need at least 6 distinct input sizes"
        )

    elif delta < 2:

        classification = (
            "Inconclusive: competing models have similar BIC"
        )

    elif not np.isfinite(best_validation_error):

        classification = (
            f"Tentative {complexity}: "
            "validation unavailable or unstable"
        )

    elif best_validation_error > 50:

        classification = (
            f"Tentative {complexity}: poor extrapolation"
        )

    elif delta < 6:

        classification = (
            f"Some evidence for {complexity}"
        )

    elif delta < 10:

        classification = (
            f"Evidence for {complexity}"
        )

    else:

        classification = (
            f"Strong relative evidence for {complexity}"
        )

    return {

        "selected": best,

        "classification": classification,

        "bic_delta": delta,

        "validation_error": best_validation_error
    }


# =====================================================
# 9. NORMALIZED COST
# =====================================================

def calculate_normalized(N, cycles):

    N = np.asarray(N, dtype=float)

    cycles = np.asarray(cycles, dtype=float)

    # Exponential normalization is stored in logarithmic
    # form to avoid numerical underflow.

    return {

        "C_over_1": cycles,

        "C_over_logN": (
            cycles / np.log(N)
        ),

        "C_over_N": (
            cycles / N
        ),

        "C_over_NlogN": (
            cycles / (N * np.log(N))
        ),

        "C_over_N2": (
            cycles / (N**2)
        ),

        "C_over_N3": (
            cycles / (N**3)
        ),

        "log_C_over_2powN": (
            np.log(cycles) - N * np.log(2.0)
        )
    }


# =====================================================
# 10. SAVE CSV OUTPUTS
# =====================================================

def save_csv(path, rows):

    if not rows:
        return

    with path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys())
        )

        writer.writeheader()

        writer.writerows(rows)


# =====================================================
# 11. SAFE PLOT NAMES
# =====================================================

def safe_name(name):

    return re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        name
    )


# =====================================================
# 12. GENERATE INDIVIDUAL PLOTS
# =====================================================

def generate_plots(
    workload,
    N,
    cycles,
    results,
    best_model,
    slope
):

    slug = safe_name(workload)

    best = results[best_model]

    predicted = best["predictions"]

    # -------------------------------------
    # PLOT 1: LINEAR AXES
    # -------------------------------------

    plt.figure()

    plt.plot(
        N,
        cycles,
        "o-",
        label="Measured median cycles"
    )

    plt.plot(
        N,
        predicted,
        "--",
        label=f"BIC-selected: {best_model}"
    )

    plt.xlabel("Input size N")

    plt.ylabel("ROI CPU cycles")

    plt.title(
        f"Cycles vs N: {workload}"
    )

    plt.legend()

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        PLOTS_DIR / f"linear_{slug}.png",
        dpi=200
    )

    plt.close()

    # -------------------------------------
    # PLOT 2: LOG-LOG
    # -------------------------------------

    plt.figure()

    plt.loglog(
        N,
        cycles,
        "o-",
        label="Measured median cycles"
    )

    positive = (
        np.isfinite(predicted)
        & (predicted > 0)
    )

    plt.loglog(
        N[positive],
        predicted[positive],
        "--",
        label=f"BIC-selected: {best_model}"
    )

    plt.xlabel("Input size N (log scale)")

    plt.ylabel("ROI CPU cycles (log scale)")

    plt.title(
        f"Log-log analysis: {workload} "
        f"(slope={slope:.3f})"
    )

    plt.legend()

    plt.grid(True, which="both")

    plt.tight_layout()

    plt.savefig(
        PLOTS_DIR / f"loglog_{slug}.png",
        dpi=200
    )

    plt.close()

    # -------------------------------------
    # PLOT 3: NORMALIZED COST
    # -------------------------------------

    normalized = calculate_normalized(
        N,
        cycles
    )

    plt.figure()

    for name in [
        "C_over_1",
        "C_over_logN",
        "C_over_N",
        "C_over_NlogN",
        "C_over_N2",
        "C_over_N3"
    ]:

        values = normalized[name]

        if (
            np.all(values > 0)
            and np.all(np.isfinite(values))
        ):

            plt.loglog(
                N,
                values,
                "o-",
                label=name
            )

    plt.xlabel("Input size N (log scale)")

    plt.ylabel("Normalized cycles (log scale)")

    plt.title(
        f"Normalized cost: {workload}"
    )

    plt.legend()

    plt.grid(True, which="both")

    plt.tight_layout()

    plt.savefig(
        PLOTS_DIR / f"normalized_{slug}.png",
        dpi=200
    )

    plt.close()

    # -------------------------------------
    # PLOT 4: ACTUAL VS PREDICTED
    # -------------------------------------

    plt.figure()

    plt.scatter(
        cycles,
        predicted,
        label="Measurements"
    )

    low = float(
        min(
            np.min(cycles),
            np.min(predicted)
        )
    )

    high = float(
        max(
            np.max(cycles),
            np.max(predicted)
        )
    )

    plt.plot(
        [low, high],
        [low, high],
        "--",
        label="Perfect prediction"
    )

    plt.xlabel("Actual cycles")

    plt.ylabel("Predicted cycles")

    plt.title(
        f"Actual vs predicted: {workload}"
    )

    plt.legend()

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        PLOTS_DIR / f"prediction_{slug}.png",
        dpi=200
    )

    plt.close()

    # -------------------------------------
    # PLOT 5: RESIDUALS
    # -------------------------------------

    residuals = (
        cycles - predicted
    )

    plt.figure()

    plt.axhline(
        0,
        linestyle="--"
    )

    plt.scatter(
        N,
        residuals
    )

    plt.xlabel("Input size N")

    plt.ylabel("Residual cycles")

    plt.title(
        f"Residual analysis: {workload}"
    )

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        PLOTS_DIR / f"residuals_{slug}.png",
        dpi=200
    )

    plt.close()


# =====================================================
# 13. ALL-WORKLOAD COMPARISON GRAPH
# =====================================================
def generate_comparison_plot(data):

    # ----------------------------------
    # GRAPH 1: RAW CPU CYCLES
    # ----------------------------------

    plt.figure(figsize=(10, 7))

    for workload, values in data.items():

        N = values["N"]
        cycles = values["cycles"]

        plt.loglog(
            N,
            cycles,
            marker="o",
            label=workload
        )

    plt.xlabel("Input size N")
    plt.ylabel("Median ROI CPU cycles")
    plt.title("Actual Workload Performance Comparison")

    plt.legend()
    plt.grid(True, which="both", alpha=0.3)

    plt.tight_layout()

    plt.savefig(
        PLOTS_DIR / "all_workloads_loglog.png",
        dpi=250
    )

    plt.close()

    # ----------------------------------
    # GRAPH 2: NORMALIZED GROWTH
    # ----------------------------------

    plt.figure(figsize=(10, 7))

    for workload, values in data.items():

        N = values["N"]
        cycles = values["cycles"]

        relative_N = N / N[0]

        relative_cycles = cycles / cycles[0]

        plt.loglog(
            relative_N,
            relative_cycles,
            marker="o",
            label=workload
        )

    plt.xlabel("Relative input size N / N_min")
    plt.ylabel("Relative cycles C(N) / C(N_min)")

    plt.title("Normalized Empirical Growth Comparison")

    plt.legend()
    plt.grid(True, which="both", alpha=0.3)

    plt.tight_layout()

    plt.savefig(
        PLOTS_DIR / "normalized_workload_comparison.png",
        dpi=250
    )

    plt.close()


# =====================================================
# 14. MAIN ANALYSIS
# =====================================================

def main():

    print("=" * 60)

    print("AUTOMATIC COMPLEXITY ANALYSIS")

    print("=" * 60)

    data = load_data()

    all_comparisons = []

    all_summaries = []

    all_predictions = []

    all_normalized = []

    for workload, values in data.items():

        N = values["N"]

        cycles = values["cycles"]

        print("\n" + "-" * 55)

        print("WORKLOAD:", workload)

        print("-" * 55)

        if len(N) < 6:

            print(
                "Skipping model classification: "
                "need at least 6 distinct N values."
            )

            continue

        models = get_models(N)

        results = {}

        for name, X in models.items():

            result = fit_model(
                X,
                cycles
            )

            result["validation_error"] = (
                validation_error(
                    X,
                    cycles
                )
            )

            results[name] = result

            all_comparisons.append({

                "workload": workload,

                "model": name,

                "valid": result["valid"],

                "parameters": result["parameters"],

                "RSS": result["rss"],

                "R2": result["r2"],

                "AIC": result["aic"],

                "AICc": result["aicc"],

                "BIC": result["bic"],

                "validation_MAPE_percent": (
                    result["validation_error"]
                ),

                # Coefficients refer to the scaled
                # feature matrices in get_models().

                "scaled_coefficients": ";".join(
                    f"{value:.12g}"
                    for value in result["coefficients"]
                )
            })

        # IMPORTANT:
        # The function accepts exactly two arguments.

        selection = select_model(
            results,
            len(N)
        )

        best_model = selection["selected"]

        slope, loglog_r2 = (
            calculate_loglog_slope(
                N,
                cycles
            )
        )

        classification = (
            selection["classification"]
        )

        print(
            "Selected candidate:",
            best_model
        )

        print(
            "Empirical classification:",
            classification
        )

        print(
            "Log-log slope:",
            round(slope, 5)
        )

        print(
            "Log-log R2:",
            round(loglog_r2, 6)
        )

        if best_model != "none":

            best = results[best_model]

            print(
                "Model R2:",
                round(best["r2"], 6)
            )

            print(
                "Model BIC:",
                round(best["bic"], 4)
            )

            print(
                "BIC delta:",
                round(selection["bic_delta"], 4)
            )

            print(
                "Validation MAPE:",
                round(best["validation_error"], 4),
                "%"
            )

            generate_plots(
                workload,
                N,
                cycles,
                results,
                best_model,
                slope
            )

            prediction = best["predictions"]

            for index in range(len(N)):

                all_predictions.append({

                    "workload": workload,

                    "N": N[index],

                    "actual_cycles": cycles[index],

                    "predicted_cycles": prediction[index],

                    "selected_model": best_model
                })

        # Normalized cost data.

        normalized = calculate_normalized(
            N,
            cycles
        )

        for index in range(len(N)):

            row = {

                "workload": workload,

                "N": N[index],

                "actual_cycles": cycles[index]
            }

            for name, values2 in normalized.items():

                row[name] = values2[index]

            all_normalized.append(row)

        # Final summary row.

        all_summaries.append({

            "workload": workload,

            "selected_model": best_model,

            "selected_complexity": (
                COMPLEXITY_NAMES.get(
                    best_model,
                    "Inconclusive"
                )
            ),

            "empirical_classification": classification,

            "loglog_slope": slope,

            "loglog_R2": loglog_r2,

            "bic_delta": selection["bic_delta"],

            "selected_model_validation_MAPE_percent": (
                selection["validation_error"]
            ),

            "number_of_input_sizes": len(N),

            "number_of_measurements": values["runs"]
        })

    if not all_summaries:

        raise RuntimeError(
            "No workload had at least six distinct input sizes. "
            "Collect more N values before running regression."
        )

    # -------------------------------------
    # SAVE ALL RESULT FILES
    # -------------------------------------

    save_csv(
        RESULTS_DIR / "model_comparison.csv",
        all_comparisons
    )

    save_csv(
        RESULTS_DIR / "summary.csv",
        all_summaries
    )

    save_csv(
        RESULTS_DIR / "fitted_predictions.csv",
        all_predictions
    )

    save_csv(
        RESULTS_DIR / "normalized_cost.csv",
        all_normalized
    )

    # Only include workloads with enough input
    # sizes in the final comparison graph.

    plottable_data = {

        workload: values

        for workload, values in data.items()

        if len(values["N"]) >= 6
    }

    generate_comparison_plot(
        plottable_data
    )

    print("\n" + "=" * 60)

    print("AUTOMATIC ANALYSIS COMPLETE")

    print("Results:", RESULTS_DIR)

    print("Plots:", PLOTS_DIR)

    print("=" * 60)


# =====================================================
# 15. ENTRY POINT
# =====================================================

if __name__ == "__main__":

    main()
