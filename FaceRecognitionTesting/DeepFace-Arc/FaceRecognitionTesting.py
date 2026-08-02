"""Store one reference embedding and verify captured face images against it."""

import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any
from typing import cast

# Prevent third-party Unicode log messages from crashing in older Windows consoles.
if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    getattr(sys.stderr, "reconfigure")(errors="replace")

try:
    from deepface import DeepFace
except Exception as import_error:
    DeepFace = None  # type: ignore[assignment, misc]
    DEEPFACE_IMPORT_ERROR: Exception | None = import_error
else:
    DEEPFACE_IMPORT_ERROR = None


SCRIPT_DIRECTORY = Path(__file__).resolve().parent

# Change these paths when testing with different local images.
REFERENCE_IMAGE_PATH = SCRIPT_DIRECTORY / "test_images/Screenshot 2026-08-02 011524.png"
CAPTURED_IMAGE_PATH = SCRIPT_DIRECTORY / "test_images/Ref_5.jpeg"
REFERENCE_EMBEDDING_PATH = SCRIPT_DIRECTORY / "stored_embeddings/reference_embedding.json"

MODEL_NAME = "ArcFace"  # ArcFace, Dlib, Facenet, OpenFace, DeepFace, DeepID, VGG-Face
DETECTOR_BACKEND = "retinaface"
DISTANCE_METRIC = "cosine"


def _deepface_is_available() -> bool:
    """Print a helpful error if DeepFace could not be imported."""
    if DeepFace is not None:
        return True

    print("Error: DeepFace or one of its dependencies could not be initialized.")
    print(f"Details: {DEEPFACE_IMPORT_ERROR}")
    return False


def _print_processing_error(error: Exception) -> None:
    """Print a readable explanation for expected image and model errors."""
    message = str(error)
    normalized_message = message.lower()

    if "face could not be detected" in normalized_message or "no face" in normalized_message:
        print(f"Error: No valid face was detected. DeepFace said: {message}")
    elif any(
        phrase in normalized_message
        for phrase in ("invalid image", "failed to load", "could not load", "cannot identify file")
    ):
        print(f"Error: The image is invalid or unreadable. DeepFace said: {message}")
    elif any(
        phrase in normalized_message
        for phrase in ("tensorflow", "keras", "model", "weight", "dependency", "package")
    ):
        print(f"Error: DeepFace or a model dependency failed to initialize. Details: {message}")
    else:
        print(f"Error: DeepFace could not process the face image. Details: {message}")


def create_reference_embedding(
    reference_image_path: Path, embedding_path: Path
) -> bool:
    """Generate and store the reference embedding during initial enrolment."""
    if not reference_image_path.is_file():
        print(f"Error: Reference image file not found: {reference_image_path}")
        return False

    if not _deepface_is_available():
        return False

    print("No stored reference embedding was found.")
    print(f"Creating it from: {reference_image_path}")

    try:
        # DeepFace is imported dynamically and static checkers may treat it as None.
        df = cast(Any, DeepFace)
        representations = cast(list, df.represent(
            img_path=str(reference_image_path),
            model_name=MODEL_NAME,
            detector_backend=DETECTOR_BACKEND,
            align=True,
            enforce_detection=True,
            max_faces=2,
        ))

        if len(representations) != 1:
            print(
                "Error: The reference image must contain exactly one valid face; "
                f"DeepFace returned {len(representations)} faces."
            )
            return False

        embedding = representations[0].get("embedding")
        if not isinstance(embedding, list) or not embedding:
            print("Error: DeepFace did not return a valid reference embedding.")
            return False

        stored_data = {
            "model": MODEL_NAME,
            "detector_backend": DETECTOR_BACKEND,
            "distance_metric": DISTANCE_METRIC,
            "source_image": reference_image_path.name,
            "embedding": embedding,
        }

        embedding_path.parent.mkdir(parents=True, exist_ok=True)
        embedding_path.write_text(json.dumps(stored_data, indent=2), encoding="utf-8")
    except (ValueError, OSError, RuntimeError) as error:
        _print_processing_error(error)
        return False
    except Exception as error:
        print(f"Error: An unexpected enrolment error occurred: {error}")
        return False

    print(f"Reference embedding stored successfully: {embedding_path}")
    return True


def load_reference_embedding(embedding_path: Path) -> list[float] | None:
    """Load and validate the stored ArcFace reference embedding."""
    try:
        stored_data = json.loads(embedding_path.read_text(encoding="utf-8"))

        if stored_data.get("model") != MODEL_NAME:
            raise ValueError(
                f"Stored embedding uses {stored_data.get('model')!r}, not {MODEL_NAME!r}."
            )
        if stored_data.get("distance_metric") != DISTANCE_METRIC:
            raise ValueError("Stored embedding uses a different distance metric.")

        embedding = stored_data.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise ValueError("The stored embedding is missing or empty.")
        if not all(isinstance(value, (int, float)) for value in embedding):
            raise ValueError("The stored embedding contains invalid values.")

        return [float(value) for value in embedding]
    except FileNotFoundError:
        print(f"Error: Stored reference embedding not found: {embedding_path}")
    except (json.JSONDecodeError, OSError, ValueError) as error:
        print(f"Error: The stored reference embedding is invalid: {error}")
        print("Delete the embedding file and run the script again to re-enrol the reference image.")

    return None


def verify_captured_face(embedding_path: Path, captured_image_path: Path) -> None:
    """Process only the captured image and compare it with the stored embedding."""
    if not captured_image_path.is_file():
        print(f"Error: Captured image file not found: {captured_image_path}")
        return

    if not _deepface_is_available():
        return

    reference_embedding = load_reference_embedding(embedding_path)
    if reference_embedding is None:
        return

    started_at = perf_counter()

    try:
        df = cast(Any, DeepFace)
        captured_representations = cast(list, df.represent(
            img_path=str(captured_image_path),
            model_name=MODEL_NAME,
            detector_backend=DETECTOR_BACKEND,
            align=True,
            enforce_detection=True,
            max_faces=2,
        ))

        if len(captured_representations) != 1:
            print(
                "Error: The captured image must contain exactly one valid face; "
                f"DeepFace returned {len(captured_representations)} faces."
            )
            return

        captured_embedding = captured_representations[0].get("embedding")
        if not isinstance(captured_embedding, list) or not captured_embedding:
            print("Error: DeepFace did not return a valid captured-image embedding.")
            return

        # Both arguments are embeddings, so DeepFace applies its official ArcFace
        # cosine threshold without decoding or processing the reference image again.
        result: dict[str, Any] = cast(dict, df.verify(
            img1_path=reference_embedding,
            img2_path=captured_embedding,
            model_name=MODEL_NAME,
            detector_backend=DETECTOR_BACKEND,
            distance_metric=DISTANCE_METRIC,
            align=True,
            enforce_detection=True,
            silent=True,
        ))

        comparison_time = result.get("time")
        result["time"] = round(perf_counter() - started_at, 2)
        result["embedding_comparison_time"] = comparison_time
        result["facial_areas"]["img2"] = captured_representations[0].get("facial_area")
        result["captured_face_confidence"] = captured_representations[0].get(
            "face_confidence"
        )
    except (ValueError, OSError, RuntimeError) as error:
        _print_processing_error(error)
        return
    except Exception as error:
        print(f"Error: An unexpected verification error occurred: {error}")
        return

    verified = bool(result.get("verified", False))

    print("\nStored-Embedding Verification Summary")
    print("-------------------------------------")
    print(f"Verified: {verified}")
    print(f"Distance: {result.get('distance', 'Not returned')}")
    print(f"Threshold: {result.get('threshold', 'Not returned')}")
    print(f"Recognition model: {result.get('model', MODEL_NAME)}")
    print(f"Detector backend: {DETECTOR_BACKEND}")
    print(f"Similarity metric: {result.get('similarity_metric', DISTANCE_METRIC)}")
    print(f"Total captured-image verification time: {result['time']} seconds")

    if verified:
        print("Result: The captured image appears to belong to the enrolled person.")
    else:
        print("Result: The captured image does not appear to belong to the enrolled person.")

    print("\nRaw DeepFace result:")
    print(result)


def main() -> None:
    """Create the reference embedding once, then verify the captured image."""
    if not REFERENCE_EMBEDDING_PATH.is_file():
        if not create_reference_embedding(REFERENCE_IMAGE_PATH, REFERENCE_EMBEDDING_PATH):
            return

    verify_captured_face(REFERENCE_EMBEDDING_PATH, CAPTURED_IMAGE_PATH)


if __name__ == "__main__":
    main()
