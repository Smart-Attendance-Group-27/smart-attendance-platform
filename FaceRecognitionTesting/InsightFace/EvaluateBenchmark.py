"""Evaluate saved InsightFace embeddings and write a model-specific report."""

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from statistics import mean, median
from typing import Any

import numpy as np


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
BENCHMARK_DATA_ROOT = SCRIPT_DIRECTORY / "benchmark_data"
REPORTS_DIRECTORY = SCRIPT_DIRECTORY / "benchmark_reports"

# Change these values manually when evaluating another generated model dataset.
MODEL_PACK_NAME = "buffalo_l"

# Temporary benchmark threshold. Calibrate this using the generated genuine and
# fake/impostor scores; do not assume one threshold is correct for every model.
SIMILARITY_THRESHOLD = 0.60


def safe_model_name(model_name: str) -> str:
    """Convert a model name into a safe filename component."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model_name).strip("._")


def load_json(path: Path) -> dict[str, Any]:
    """Load one required JSON benchmark file."""
    if not path.is_file():
        raise FileNotFoundError(f"Required benchmark file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_embedding(values: Any, embedding_id: str) -> np.ndarray:
    """Validate and normalize one saved embedding before comparison."""
    if not isinstance(values, list) or not values:
        raise ValueError(f"Invalid or empty embedding: {embedding_id}")

    embedding = np.asarray(values, dtype=np.float32).reshape(-1)
    embedding_norm = float(np.linalg.norm(embedding))
    if embedding_norm == 0.0 or not np.isfinite(embedding_norm):
        raise ValueError(f"Embedding has an invalid L2 norm: {embedding_id}")
    return embedding / embedding_norm


def cosine_similarity(embedding_one: np.ndarray, embedding_two: np.ndarray) -> float:
    """Calculate cosine similarity between two normalized embeddings."""
    return float(np.dot(embedding_one, embedding_two))


def safe_rate(numerator: int, denominator: int) -> float | None:
    """Return a rate or None when the dataset has no required samples."""
    return numerator / denominator if denominator else None


def value_summary(values: list[float]) -> dict[str, float | int | None]:
    """Return useful summary statistics for similarities or latencies."""
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p95": None,
            "minimum": None,
            "maximum": None,
        }

    return {
        "count": len(values),
        "mean": round(mean(values), 6),
        "median": round(median(values), 6),
        "p95": round(float(np.percentile(values, 95)), 6),
        "minimum": round(min(values), 6),
        "maximum": round(max(values), 6),
    }


def evaluate_pair_list(
    pairs: list[dict[str, str]],
    pair_type: str,
    reference_embeddings: dict[str, np.ndarray],
    captured_embeddings: dict[str, np.ndarray],
) -> list[dict[str, Any]]:
    """Resolve saved pair IDs and calculate one cosine score per pair."""
    scored_pairs: list[dict[str, Any]] = []

    for pair in pairs:
        reference_id = pair["reference_user_id"]
        captured_id = pair["captured_embedding_id"]

        if reference_id not in reference_embeddings:
            raise ValueError(f"Pair refers to a missing reference embedding: {reference_id}")
        if captured_id not in captured_embeddings:
            raise ValueError(f"Pair refers to a missing captured embedding: {captured_id}")

        similarity = cosine_similarity(
            reference_embeddings[reference_id],
            captured_embeddings[captured_id],
        )
        accepted = similarity >= SIMILARITY_THRESHOLD
        expected_acceptance = pair_type == "genuine"

        scored_pairs.append(
            {
                "pair_type": pair_type,
                "reference_user_id": reference_id,
                "captured_embedding_id": captured_id,
                "captured_user_id": pair["captured_user_id"],
                "cosine_similarity": round(similarity, 6),
                "accepted": accepted,
                "correct_decision": accepted == expected_acceptance,
            }
        )

    return scored_pairs


def percentage_text(value: float | None) -> str:
    """Format a rate as a readable percentage."""
    return "Not available" if value is None else f"{value * 100:.4f}%"


def seconds_text(value: float | None) -> str:
    """Format an optional latency value."""
    return "Not available" if value is None else f"{value:.6f} seconds"


def write_pair_scores(path: Path, scored_pairs: list[dict[str, Any]]) -> None:
    """Write auditable per-pair scores for later threshold analysis."""
    fieldnames = [
        "pair_type",
        "reference_user_id",
        "captured_embedding_id",
        "captured_user_id",
        "cosine_similarity",
        "accepted",
        "correct_decision",
    ]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scored_pairs)


def main() -> None:
    """Calculate verification metrics and write JSON, text, and pair-score files."""
    if not -1.0 <= SIMILARITY_THRESHOLD <= 1.0:
        raise ValueError("SIMILARITY_THRESHOLD must be between -1.0 and 1.0.")

    model_directory = BENCHMARK_DATA_ROOT / safe_model_name(MODEL_PACK_NAME)
    benchmark_data = load_json(model_directory / "benchmark_data.json")
    genuine_data = load_json(model_directory / "genuine_pairs.json")
    fake_data = load_json(model_directory / "fake_pairs.json")

    generated_model = benchmark_data.get("model", {}).get("model_pack")
    if generated_model != MODEL_PACK_NAME:
        raise ValueError(
            f"Generated data uses model {generated_model!r}, not {MODEL_PACK_NAME!r}."
        )

    reference_embeddings = {
        user_id: normalized_embedding(data["embedding"], f"reference:{user_id}")
        for user_id, data in benchmark_data["reference_embeddings"].items()
    }
    captured_embeddings = {
        captured_id: normalized_embedding(data["embedding"], f"captured:{captured_id}")
        for captured_id, data in benchmark_data["captured_embeddings"].items()
    }

    genuine_scores = evaluate_pair_list(
        genuine_data["pairs"],
        "genuine",
        reference_embeddings,
        captured_embeddings,
    )
    fake_scores = evaluate_pair_list(
        fake_data["pairs"],
        "fake_impostor",
        reference_embeddings,
        captured_embeddings,
    )
    all_scores = genuine_scores + fake_scores

    true_acceptances = sum(score["accepted"] for score in genuine_scores)
    false_rejections = len(genuine_scores) - true_acceptances
    false_acceptances = sum(score["accepted"] for score in fake_scores)
    true_rejections = len(fake_scores) - false_acceptances

    far = safe_rate(false_acceptances, len(fake_scores))
    frr = safe_rate(false_rejections, len(genuine_scores))
    true_acceptance_rate = safe_rate(true_acceptances, len(genuine_scores))

    image_statistics = benchmark_data["image_statistics"]
    detection_failure_rate = safe_rate(
        image_statistics["failed"],
        image_statistics["attempted"],
    )

    latency = benchmark_data["latency"]
    warm_latency_summary = value_summary(latency["warm_inference_seconds"])
    genuine_similarity_summary = value_summary(
        [score["cosine_similarity"] for score in genuine_scores]
    )
    fake_similarity_summary = value_summary(
        [score["cosine_similarity"] for score in fake_scores]
    )

    warnings_list: list[str] = []
    if not genuine_scores:
        warnings_list.append("No genuine pairs were available; FRR and TAR are undefined.")
    if not fake_scores:
        warnings_list.append("No fake/impostor pairs were available; FAR is undefined.")
    if warm_latency_summary["count"] == 0:
        warnings_list.append("No post-first-inference samples were available for warm latency.")

    report_created_at = datetime.now(timezone.utc)
    report = {
        "schema_version": 1,
        "report_created_at_utc": report_created_at.isoformat(),
        "benchmark_generated_at_utc": benchmark_data["generated_at_utc"],
        "model": benchmark_data["model"],
        "similarity_threshold": SIMILARITY_THRESHOLD,
        "metrics": {
            "false_acceptance_rate": far,
            "false_rejection_rate": frr,
            "true_acceptance_rate": true_acceptance_rate,
            "detection_failure_rate": detection_failure_rate,
        },
        "decision_counts": {
            "true_acceptances": true_acceptances,
            "false_rejections": false_rejections,
            "false_acceptances": false_acceptances,
            "true_rejections": true_rejections,
            "genuine_pairs": len(genuine_scores),
            "fake_impostor_pairs": len(fake_scores),
        },
        "latency_seconds": {
            "model_initialization": latency["model_initialization_seconds"],
            "first_inference": latency["first_inference_seconds"],
            "cold_start": latency["cold_start_seconds"],
            "warm_inference": warm_latency_summary,
        },
        "image_statistics": image_statistics,
        "similarity_distributions": {
            "genuine": genuine_similarity_summary,
            "fake_impostor": fake_similarity_summary,
        },
        "warnings": warnings_list,
    }

    timestamp = report_created_at.strftime("%Y%m%dT%H%M%SZ")
    report_base_name = (
        f"{safe_model_name(MODEL_PACK_NAME)}_threshold_"
        f"{SIMILARITY_THRESHOLD:.4f}_{timestamp}"
    )
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    json_report_path = REPORTS_DIRECTORY / f"{report_base_name}.json"
    text_report_path = REPORTS_DIRECTORY / f"{report_base_name}.txt"
    pair_scores_path = REPORTS_DIRECTORY / f"{report_base_name}_pair_scores.csv"

    json_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_pair_scores(pair_scores_path, all_scores)

    warm_mean = warm_latency_summary["mean"]
    report_lines = [
        "InsightFace Multi-User Verification Benchmark",
        "=============================================",
        f"Model pack: {MODEL_PACK_NAME}",
        f"Execution provider: {benchmark_data['model']['execution_provider']}",
        f"Detection size: {benchmark_data['model']['detection_size']}",
        f"Comparison metric: Cosine similarity",
        f"Similarity threshold: {SIMILARITY_THRESHOLD:.4f}",
        "",
        "Verification metrics",
        "--------------------",
        f"False acceptance rate (FAR): {percentage_text(far)}",
        f"False rejection rate (FRR): {percentage_text(frr)}",
        f"True acceptance rate (TAR): {percentage_text(true_acceptance_rate)}",
        f"Detection failure rate: {percentage_text(detection_failure_rate)}",
        "",
        "Latency",
        "-------",
        f"Model initialization: {seconds_text(latency['model_initialization_seconds'])}",
        f"First inference: {seconds_text(latency['first_inference_seconds'])}",
        f"Cold-start latency: {seconds_text(latency['cold_start_seconds'])}",
        f"Warm inference latency (mean): {seconds_text(warm_mean)}",
        f"Warm inference samples: {warm_latency_summary['count']}",
        "",
        "Decision counts",
        "---------------",
        f"True acceptances: {true_acceptances}",
        f"False rejections: {false_rejections}",
        f"False acceptances: {false_acceptances}",
        f"True rejections: {true_rejections}",
        f"Genuine pairs: {len(genuine_scores)}",
        f"Fake/impostor pairs: {len(fake_scores)}",
        "",
        "Image processing",
        "----------------",
        f"Attempted images: {image_statistics['attempted']}",
        f"Successful embeddings: {image_statistics['successful']}",
        f"Detection/processing failures: {image_statistics['failed']}",
    ]
    if warnings_list:
        report_lines.extend(["", "Warnings", "--------", *warnings_list])

    text_report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("\n".join(report_lines))
    print()
    print(f"JSON report: {json_report_path}")
    print(f"Text report: {text_report_path}")
    print(f"Pair scores: {pair_scores_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Benchmark evaluation failed: {error}")
