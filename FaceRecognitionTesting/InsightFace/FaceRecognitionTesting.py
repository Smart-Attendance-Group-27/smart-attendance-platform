"""Run a simple one-to-one face-verification test with InsightFace."""

import cv2
import numpy as np
from insightface.app import FaceAnalysis


REFERENCE_IMAGE_PATH = "test_images/Ref_8.jpeg"
CAPTURED_IMAGE_PATH = "test_images/Ref_10.jpeg"

MODEL_PACK_NAME = "buffalo_l"
DETECTION_SIZE = (640, 640)

# The threshold of 0.40 is only an initial experimental value for this mock.
# It must not be treated as a production threshold. The final threshold must
# be selected after evaluating genuine and impostor student image pairs under
# realistic university attendance conditions.
SIMILARITY_THRESHOLD = 0.60


def create_face_analyzer() -> FaceAnalysis:
    """Initialize the InsightFace models once for CPU execution."""
    face_analyzer = FaceAnalysis(
        name=MODEL_PACK_NAME,
        providers=["CPUExecutionProvider"],
    )
    face_analyzer.prepare(
        ctx_id=-1,
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


def verify_faces(
    reference_image_path: str,
    captured_image_path: str,
) -> None:
    """Process two images and make a temporary threshold-based decision."""
    print("InsightFace one-to-one verification")
    print("-----------------------------------")
    print()

    # Initialize the model only once and reuse it for both images.
    face_analyzer = create_face_analyzer()

    # Do not resize, crop, align, normalize pixels, or change colour channels
    # here. InsightFace controls its required face preprocessing internally.
    reference_image = load_image(reference_image_path)
    captured_image = load_image(captured_image_path)

    reference_embedding = extract_embedding(
        face_analyzer,
        reference_image,
        "reference",
    )
    captured_embedding = extract_embedding(
        face_analyzer,
        captured_image,
        "captured",
    )

    if reference_embedding.shape != captured_embedding.shape:
        raise ValueError(
            "Embedding dimensions do not match: "
            f"{reference_embedding.size} and {captured_embedding.size}."
        )

    cosine_similarity = calculate_cosine_similarity(
        reference_embedding,
        captured_embedding,
    )
    verified = cosine_similarity >= SIMILARITY_THRESHOLD

    print(f"Model pack: {MODEL_PACK_NAME}")
    print("Detector and recognition pipeline: InsightFace FaceAnalysis")
    print("Execution provider: CPUExecutionProvider")
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


# This mock processes both images on every run and is suitable only for testing.
# A future enrolment pipeline should generate and store the reference embedding
# once. During attendance, only the newly captured image embedding should
# normally be generated and compared with the stored reference embedding.
if __name__ == "__main__":
    try:
        verify_faces(
            REFERENCE_IMAGE_PATH,
            CAPTURED_IMAGE_PATH,
        )
    except Exception as error:
        print(f"Face verification failed: {error}")
