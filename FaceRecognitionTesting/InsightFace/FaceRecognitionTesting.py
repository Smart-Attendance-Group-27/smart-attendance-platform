"""Run a simple one-to-one face-verification test with InsightFace."""

import json
from pathlib import Path
from time import perf_counter
import warnings

import cv2
import numpy as np
import onnxruntime as ort
from insightface.app import FaceAnalysis


# InsightFace 1.0.1 currently calls an API that scikit-image has deprecated.
# This narrow filter hides only that known third-party compatibility notice.
warnings.filterwarnings(
    "ignore",
    message=r"`estimate` is deprecated.*",
    category=FutureWarning,
    module=r"insightface\.utils\.face_align",
)


REFERENCE_IMAGE_PATH = "reference_images/Screenshot 2026-08-02 011524.png"
CAPTURED_IMAGE_PATH = "capture_images/Ref_6.jpeg"
REFERENCE_EMBEDDING_PATH = "stored_embeddings/reference_embedding.json"

MODEL_PACK_NAME = "buffalo_l"
DETECTION_SIZE = (640, 640)

# Prefer CUDA when the GPU-enabled ONNX Runtime package is available. Otherwise,
# select CPU explicitly instead of asking ONNX Runtime for an unavailable provider.
AVAILABLE_EXECUTION_PROVIDERS = ort.get_available_providers()
if "CUDAExecutionProvider" in AVAILABLE_EXECUTION_PROVIDERS:
    EXECUTION_PROVIDERS = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    EXECUTION_CONTEXT_ID = 0
else:
    EXECUTION_PROVIDERS = ["CPUExecutionProvider"]
    EXECUTION_CONTEXT_ID = -1

# The threshold of 0.40 is only an initial experimental value for this mock.
# It must not be treated as a production threshold. The final threshold must
# be selected after evaluating genuine and impostor student image pairs under
# realistic university attendance conditions.
SIMILARITY_THRESHOLD = 0.60


def create_face_analyzer() -> FaceAnalysis:
    """Initialize the InsightFace models once using an available provider."""
    face_analyzer = FaceAnalysis(
        name=MODEL_PACK_NAME,
        providers=EXECUTION_PROVIDERS,
        # Verification needs only face detection and recognition. Excluding
        # age, gender, and extra landmark models avoids unrelated inference.
        allowed_modules=["detection", "recognition"],
    )
    face_analyzer.prepare(
        ctx_id=EXECUTION_CONTEXT_ID,
        det_size=DETECTION_SIZE,
    )
    return face_analyzer


def load_image(image_path: str) -> np.ndarray:
    """Read an image without changing InsightFace's expected input data."""
    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(f"OpenCV could not read the image: {image_path}")

    return image


def extract_embedding(
    face_analyzer: FaceAnalysis,
    image: np.ndarray,
    image_label: str,
) -> np.ndarray:
    """Detect exactly one face and return its normalized recognition embedding."""
    # FaceAnalysis.get() performs face detection and runs the configured
    # face-analysis models, including the recognition model used here.
    faces = face_analyzer.get(image)

    if len(faces) == 0:
        raise ValueError(f"No face detected in the {image_label} image.")

    if len(faces) > 1:
        raise ValueError(
            f"Multiple faces detected in the {image_label} image; "
            "this one-to-one test requires exactly one face."
        )

    face = faces[0]

    # normed_embedding is the numerical facial representation used for the
    # comparison. Older model configurations may provide only embedding.
    embedding = getattr(face, "normed_embedding", None)
    if embedding is None:
        embedding = getattr(face, "embedding", None)

    if embedding is None:
        raise ValueError(f"No recognition embedding returned for the {image_label} image.")

    normalized_embedding = np.asarray(embedding, dtype=np.float32).reshape(-1)
    embedding_norm = float(np.linalg.norm(normalized_embedding))

    if embedding_norm == 0.0 or not np.isfinite(embedding_norm):
        raise ValueError(f"Invalid recognition embedding for the {image_label} image.")

    # This also safely normalizes the fallback face.embedding value.
    normalized_embedding = normalized_embedding / embedding_norm

    bounding_box = np.asarray(face.bbox).round(2).tolist()
    detection_confidence = float(face.det_score)

    print(f"{image_label.capitalize()} image:")
    print("- Number of faces: 1")
    print(f"- Detection confidence: {detection_confidence:.4f}")
    print(f"- Bounding box: {bounding_box}")
    print(f"- Embedding dimension: {normalized_embedding.size}")
    print()

    return normalized_embedding


def calculate_cosine_similarity(
    embedding_one: np.ndarray,
    embedding_two: np.ndarray,
) -> float:
    """Calculate cosine similarity between two normalized face embeddings."""
    norm_product = float(np.linalg.norm(embedding_one) * np.linalg.norm(embedding_two))

    if norm_product == 0.0:
        raise ValueError("Cannot compare an embedding with a zero L2 norm.")

    similarity = np.dot(embedding_one, embedding_two) / norm_product
    return float(similarity)


def store_reference_embedding(
    embedding: np.ndarray,
    embedding_path: str,
    reference_image_path: str,
) -> None:
    """Save the enrolled reference embedding and its model metadata as JSON."""
    stored_data = {
        "model_pack": MODEL_PACK_NAME,
        "detection_size": list(DETECTION_SIZE),
        "source_image": reference_image_path,
        "embedding_dimension": int(embedding.size),
        "embedding": embedding.tolist(),
    }

    destination = Path(embedding_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(stored_data, indent=2),
        encoding="utf-8",
    )


def load_reference_embedding(embedding_path: str) -> np.ndarray:
    """Load and validate a previously enrolled reference embedding."""
    source = Path(embedding_path)

    try:
        stored_data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Stored reference embedding is not valid JSON: {source}") from error

    if stored_data.get("model_pack") != MODEL_PACK_NAME:
        raise ValueError(
            "Stored reference embedding uses a different model pack. "
            f"Delete {source} and run the script again to re-enrol it."
        )

    embedding_values = stored_data.get("embedding")
    if not isinstance(embedding_values, list) or not embedding_values:
        raise ValueError(f"Stored reference embedding is missing or empty: {source}")

    embedding = np.asarray(embedding_values, dtype=np.float32).reshape(-1)
    embedding_norm = float(np.linalg.norm(embedding))

    if embedding_norm == 0.0 or not np.isfinite(embedding_norm):
        raise ValueError(f"Stored reference embedding is invalid: {source}")

    expected_dimension = stored_data.get("embedding_dimension")
    if expected_dimension != embedding.size:
        raise ValueError(
            "Stored reference embedding dimension does not match its metadata. "
            f"Delete {source} and run the script again to re-enrol it."
        )

    return embedding / embedding_norm


def get_or_create_reference_embedding(
    face_analyzer: FaceAnalysis,
    reference_image_path: str,
    embedding_path: str,
) -> np.ndarray:
    """Load the stored reference embedding or create it during first enrolment."""
    if Path(embedding_path).is_file():
        print(f"Using stored reference embedding: {embedding_path}")
        print()
        return load_reference_embedding(embedding_path)

    print("No stored reference embedding was found.")
    print(f"Creating it from: {reference_image_path}")
    print()

    reference_image = load_image(reference_image_path)
    reference_embedding = extract_embedding(
        face_analyzer,
        reference_image,
        "reference",
    )
    store_reference_embedding(
        reference_embedding,
        embedding_path,
        reference_image_path,
    )

    print(f"Reference embedding stored successfully: {embedding_path}")
    print()
    return reference_embedding


def verify_faces(
    reference_image_path: str,
    captured_image_path: str,
) -> None:
    """Compare one captured face with the enrolled reference embedding."""
    total_started_at = perf_counter()

    print("InsightFace one-to-one verification")
    print("-----------------------------------")
    print()

    # Initialize the model only once. It is needed to process the captured image
    # and is also reused for reference enrolment when no stored embedding exists.
    model_started_at = perf_counter()
    face_analyzer = create_face_analyzer()
    model_initialization_time = perf_counter() - model_started_at

    # Do not resize, crop, align, normalize pixels, or change colour channels
    # here. InsightFace controls its required face preprocessing internally.
    reference_started_at = perf_counter()
    reference_embedding = get_or_create_reference_embedding(
        face_analyzer,
        reference_image_path,
        REFERENCE_EMBEDDING_PATH,
    )
    reference_embedding_time = perf_counter() - reference_started_at

    # On every run after enrolment, only this newly captured image is decoded,
    # detected, aligned, preprocessed, and passed through the recognition model.
    captured_request_started_at = perf_counter()
    image_load_started_at = perf_counter()
    captured_image = load_image(captured_image_path)
    captured_image_load_time = perf_counter() - image_load_started_at

    recognition_started_at = perf_counter()
    captured_embedding = extract_embedding(
        face_analyzer,
        captured_image,
        "captured",
    )
    captured_recognition_time = perf_counter() - recognition_started_at

    if reference_embedding.shape != captured_embedding.shape:
        raise ValueError(
            "Embedding dimensions do not match: "
            f"{reference_embedding.size} and {captured_embedding.size}."
        )

    comparison_started_at = perf_counter()
    cosine_similarity = calculate_cosine_similarity(
        reference_embedding,
        captured_embedding,
    )
    verified = cosine_similarity >= SIMILARITY_THRESHOLD
    comparison_time = perf_counter() - comparison_started_at
    captured_request_time = perf_counter() - captured_request_started_at
    total_verification_time = perf_counter() - total_started_at

    print(f"Model pack: {MODEL_PACK_NAME}")
    print("Detector and recognition pipeline: InsightFace FaceAnalysis")
    print(f"Execution provider: {EXECUTION_PROVIDERS[0]}")
    print(f"Detection size: {DETECTION_SIZE[0]} x {DETECTION_SIZE[1]}")
    print(f"Embedding dimension: {reference_embedding.size}")
    print("Comparison metric: Cosine similarity")
    print()
    print(f"Cosine similarity: {cosine_similarity:.4f}")
    print(f"Temporary threshold: {SIMILARITY_THRESHOLD:.4f}")
    print()
    print(f"Verified: {verified}")

    # InsightFace generates the embeddings, but it does not make our
    # attendance decision. This script applies the temporary threshold.
    if verified:
        print("Result: The two images appear to belong to the same person.")
    else:
        print("Result: The two images do not appear to belong to the same person.")

    print()
    print("Timing breakdown")
    print("----------------")
    print(f"Model initialization: {model_initialization_time:.4f} seconds")
    print(f"Stored embedding load/enrolment: {reference_embedding_time:.4f} seconds")
    print(f"Captured image loading: {captured_image_load_time:.4f} seconds")
    print(
        "Captured face detection, alignment and embedding: "
        f"{captured_recognition_time:.4f} seconds"
    )
    print(f"Cosine similarity and decision: {comparison_time:.6f} seconds")
    print(f"Captured-image request latency: {captured_request_time:.4f} seconds")
    print(f"Total script verification time: {total_verification_time:.4f} seconds")


# The reference image is processed only when its stored embedding is missing.
# Later runs process only the captured image and compare it with that stored
# reference representation. This JSON storage is still a local testing approach;
# production biometric data requires appropriate access control and protection.
if __name__ == "__main__":
    try:
        verify_faces(
            REFERENCE_IMAGE_PATH,
            CAPTURED_IMAGE_PATH,
        )
    except Exception as error:
        print(f"Face verification failed: {error}")
