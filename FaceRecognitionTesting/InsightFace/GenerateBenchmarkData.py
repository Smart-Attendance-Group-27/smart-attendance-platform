"""Generate InsightFace embeddings and multi-user benchmark pair files."""

import json
from datetime import datetime, timezone
from pathlib import Path
import re
from time import perf_counter
from typing import Any
import warnings

import cv2
import numpy as np
import onnxruntime as ort
from insightface.app import FaceAnalysis


SCRIPT_DIRECTORY = Path(__file__).resolve().parent

# Dataset layout:
# reference_images/user1.jpg
# capture_images/user1/img_1.jpg
REFERENCE_IMAGES_DIRECTORY = SCRIPT_DIRECTORY / "reference_images"
CAPTURED_IMAGES_DIRECTORY = SCRIPT_DIRECTORY / "capture_images"
BENCHMARK_DATA_ROOT = SCRIPT_DIRECTORY / "benchmark_data"

# Change this manually before generating data for another InsightFace model pack.
MODEL_PACK_NAME = "buffalo_l"
DETECTION_SIZE = (640, 640)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

warnings.filterwarnings(
    "ignore",
    message=r"`estimate` is deprecated.*",
    category=FutureWarning,
    module=r"insightface\.utils\.face_align",
)


def safe_model_name(model_name: str) -> str:
    """Convert a model name into a safe folder-name component."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model_name).strip("._")


def select_execution_provider() -> tuple[list[str], int]:
    """Prefer CUDA when installed, otherwise explicitly use the CPU provider."""
    available_providers = ort.get_available_providers()
    if "CUDAExecutionProvider" in available_providers:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"], 0
    return ["CPUExecutionProvider"], -1


def create_face_analyzer() -> tuple[FaceAnalysis, list[str], float]:
    """Create and prepare one analyzer while measuring cold model initialization."""
    providers, context_id = select_execution_provider()
    started_at = perf_counter()

    analyzer = FaceAnalysis(
        name=MODEL_PACK_NAME,
        providers=providers,
        allowed_modules=["detection", "recognition"],
    )
    analyzer.prepare(
        ctx_id=context_id,
        det_size=DETECTION_SIZE,
    )

    initialization_seconds = perf_counter() - started_at
    return analyzer, providers, initialization_seconds


def relative_path(path: Path) -> str:
    """Return a readable path relative to this benchmark directory."""
    try:
        return path.resolve().relative_to(SCRIPT_DIRECTORY).as_posix()
    except ValueError:
        return str(path.resolve())


def list_images(directory: Path) -> list[Path]:
    """Return supported image files in stable alphabetical order."""
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    )


def normalize_embedding(face: Any) -> np.ndarray:
    """Return a one-dimensional, L2-normalized embedding from one detected face."""
    embedding = getattr(face, "normed_embedding", None)
    if embedding is None:
        embedding = getattr(face, "embedding", None)
    if embedding is None:
        raise ValueError("InsightFace did not return a recognition embedding.")

    vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
    vector_norm = float(np.linalg.norm(vector))
    if vector_norm == 0.0 or not np.isfinite(vector_norm):
        raise ValueError("InsightFace returned an invalid recognition embedding.")
    return vector / vector_norm


def process_image(
    analyzer: FaceAnalysis,
    image_path: Path,
    image_kind: str,
    user_id: str,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Process one image and return its embedding plus latency/failure metadata."""
    record: dict[str, Any] = {
        "image_path": relative_path(image_path),
        "image_kind": image_kind,
        "user_id": user_id,
        "status": "failed",
        "failure_reason": None,
        "image_load_seconds": None,
        "inference_seconds": None,
        "total_processing_seconds": None,
    }
    total_started_at = perf_counter()

    load_started_at = perf_counter()
    image = cv2.imread(str(image_path))
    record["image_load_seconds"] = round(perf_counter() - load_started_at, 6)

    if image is None:
        record["failure_reason"] = "OpenCV could not read the image."
        record["total_processing_seconds"] = round(perf_counter() - total_started_at, 6)
        return None, record

    try:
        inference_started_at = perf_counter()
        faces = analyzer.get(image)
        record["inference_seconds"] = round(perf_counter() - inference_started_at, 6)

        if len(faces) == 0:
            raise ValueError("No face detected.")
        if len(faces) > 1:
            raise ValueError(f"Multiple faces detected ({len(faces)} faces).")

        face = faces[0]
        embedding = normalize_embedding(face)
        record.update(
            {
                "status": "success",
                "failure_reason": None,
                "detection_confidence": round(float(face.det_score), 6),
                "bounding_box": np.asarray(face.bbox).round(2).tolist(),
                "embedding_dimension": int(embedding.size),
            }
        )
    except Exception as error:
        record["failure_reason"] = str(error)
        embedding = None

    record["total_processing_seconds"] = round(perf_counter() - total_started_at, 6)
    return embedding, record


def write_json(path: Path, data: Any) -> None:
    """Write readable UTF-8 JSON, creating its parent directory when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    """Generate embeddings, genuine pairs, fake pairs, failures, and latency data."""
    reference_images = list_images(REFERENCE_IMAGES_DIRECTORY)
    if not reference_images:
        raise ValueError(
            f"No reference images found in: {REFERENCE_IMAGES_DIRECTORY}\n"
            "Add files such as user1.jpg and user2.jpg."
        )
    if not CAPTURED_IMAGES_DIRECTORY.is_dir():
        raise ValueError(f"Captured-image directory not found: {CAPTURED_IMAGES_DIRECTORY}")

    reference_user_ids = [path.stem for path in reference_images]
    if len(reference_user_ids) != len(set(reference_user_ids)):
        raise ValueError("Reference-image filenames must have unique user IDs.")

    user_directories = sorted(
        path for path in CAPTURED_IMAGES_DIRECTORY.iterdir() if path.is_dir()
    )
    if not user_directories:
        raise ValueError(
            f"No user folders found in: {CAPTURED_IMAGES_DIRECTORY}\n"
            "Move captured images into folders such as "
            "capture_images/user1/img_1.jpg."
        )

    captured_user_ids = {path.name for path in user_directories}
    matching_user_ids = set(reference_user_ids) & captured_user_ids
    if not matching_user_ids:
        raise ValueError(
            "No reference filename matches a captured-image folder name. "
            "For example, reference_images/user1.jpg must match "
            "capture_images/user1/."
        )

    print("InsightFace multi-user embedding generation")
    print("-------------------------------------------")
    print(f"Model pack: {MODEL_PACK_NAME}")

    analyzer, providers, model_initialization_seconds = create_face_analyzer()
    print(f"Execution provider: {providers[0]}")
    print(f"Model initialization: {model_initialization_seconds:.4f} seconds")
    print()

    reference_embeddings: dict[str, dict[str, Any]] = {}
    captured_embeddings: dict[str, dict[str, Any]] = {}
    image_records: list[dict[str, Any]] = []

    for image_path in reference_images:
        user_id = image_path.stem
        embedding, record = process_image(analyzer, image_path, "reference", user_id)
        image_records.append(record)
        print(f"Reference {user_id}: {record['status']}")

        if embedding is not None:
            reference_embeddings[user_id] = {
                "image_path": relative_path(image_path),
                "embedding": embedding.tolist(),
            }

    for user_directory in user_directories:
        user_id = user_directory.name
        for image_path in list_images(user_directory):
            captured_id = f"{user_id}/{image_path.name}"
            embedding, record = process_image(analyzer, image_path, "captured", user_id)
            image_records.append(record)
            print(f"Captured {captured_id}: {record['status']}")

            if embedding is not None:
                captured_embeddings[captured_id] = {
                    "user_id": user_id,
                    "image_path": relative_path(image_path),
                    "embedding": embedding.tolist(),
                }

    genuine_pairs: list[dict[str, str]] = []
    fake_pairs: list[dict[str, str]] = []

    for reference_user_id in sorted(reference_embeddings):
        for captured_id, captured_data in sorted(captured_embeddings.items()):
            pair = {
                "reference_user_id": reference_user_id,
                "captured_embedding_id": captured_id,
                "captured_user_id": captured_data["user_id"],
            }
            if captured_data["user_id"] == reference_user_id:
                genuine_pairs.append(pair)
            else:
                fake_pairs.append(pair)

    inference_records = [
        record for record in image_records if record["inference_seconds"] is not None
    ]
    first_inference_seconds = (
        inference_records[0]["inference_seconds"] if inference_records else None
    )
    cold_start_seconds = (
        round(model_initialization_seconds + first_inference_seconds, 6)
        if first_inference_seconds is not None
        else None
    )
    warm_inference_seconds = [
        record["inference_seconds"] for record in inference_records[1:]
    ]

    successful_images = sum(record["status"] == "success" for record in image_records)
    failed_images = len(image_records) - successful_images
    generated_at = datetime.now(timezone.utc).isoformat()
    model_output_directory = BENCHMARK_DATA_ROOT / safe_model_name(MODEL_PACK_NAME)

    benchmark_data = {
        "schema_version": 1,
        "generated_at_utc": generated_at,
        "model": {
            "framework": "InsightFace",
            "model_pack": MODEL_PACK_NAME,
            "detection_size": list(DETECTION_SIZE),
            "execution_provider": providers[0],
            "comparison_metric": "cosine_similarity",
        },
        "latency": {
            "model_initialization_seconds": round(model_initialization_seconds, 6),
            "first_inference_seconds": first_inference_seconds,
            "cold_start_seconds": cold_start_seconds,
            "warm_inference_seconds": warm_inference_seconds,
        },
        "image_statistics": {
            "attempted": len(image_records),
            "successful": successful_images,
            "failed": failed_images,
        },
        "image_records": image_records,
        "reference_embeddings": reference_embeddings,
        "captured_embeddings": captured_embeddings,
    }
    pair_metadata = {
        "schema_version": 1,
        "generated_at_utc": generated_at,
        "model_pack": MODEL_PACK_NAME,
    }

    write_json(model_output_directory / "benchmark_data.json", benchmark_data)
    write_json(
        model_output_directory / "genuine_pairs.json",
        {**pair_metadata, "pair_type": "genuine", "pairs": genuine_pairs},
    )
    write_json(
        model_output_directory / "fake_pairs.json",
        {**pair_metadata, "pair_type": "fake_impostor", "pairs": fake_pairs},
    )

    print()
    print("Generation summary")
    print("------------------")
    print(f"Attempted images: {len(image_records)}")
    print(f"Successful embeddings: {successful_images}")
    print(f"Detection/processing failures: {failed_images}")
    print(f"Genuine pairs: {len(genuine_pairs)}")
    print(f"Fake/impostor pairs: {len(fake_pairs)}")
    print(f"Output directory: {model_output_directory}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Benchmark data generation failed: {error}")
