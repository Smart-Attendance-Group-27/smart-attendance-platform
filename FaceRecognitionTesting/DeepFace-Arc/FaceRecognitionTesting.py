"""Run a simple one-to-one face-verification test with DeepFace and ArcFace."""

from pathlib import Path
import sys
from typing import Any

# Prevent third-party log messages containing Unicode symbols from crashing in
# Windows terminals that use a legacy console encoding.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

try:
    from deepface import DeepFace
except Exception as import_error:
    # DeepFace can raise dependency/configuration errors while it is imported.
    # Save the error so the program can report a friendly initialization message.
    DeepFace = None  # type: ignore[assignment, misc]
    DEEPFACE_IMPORT_ERROR: Exception | None = import_error
else:
    DEEPFACE_IMPORT_ERROR = None


# Change these paths to point to the two local images that you want to compare.
REFERENCE_IMAGE_PATH = "test_images/Screenshot 2026-08-02 011524.png"
CAPTURED_IMAGE_PATH = "test_images/Ref_3.jpeg"

MODEL_NAME = "ArcFace"
DETECTOR_BACKEND = "retinaface"
DISTANCE_METRIC = "cosine"


def _describe_value_error(error: ValueError) -> str:
    """Return a beginner-friendly explanation for a DeepFace input error."""
    message = str(error)
    normalized_message = message.lower()

    if "face could not be detected" in normalized_message or "no face" in normalized_message:
        return f"No valid face was detected in one of the images. DeepFace said: {message}"

    if "multiple face" in normalized_message or "more than one face" in normalized_message:
        return f"Multiple faces were found where one valid face was expected. DeepFace said: {message}"

    if any(
        phrase in normalized_message
        for phrase in ("cannot identify file", "invalid image", "failed to load", "could not load")
    ):
        return f"An image is invalid or unreadable. DeepFace said: {message}"

    if any(
        phrase in normalized_message
        for phrase in ("tensorflow", "keras", "model", "weight", "dependency", "package")
    ):
        return f"DeepFace or a required model dependency failed to initialize. Details: {message}"

    return f"DeepFace rejected an image or face as invalid. Details: {message}"


def verify_faces(reference_image_path: str, captured_image_path: str) -> None:
    """Verify whether two local images appear to show the same person."""
    image_paths = (reference_image_path, captured_image_path)
    missing_paths = [image_path for image_path in image_paths if not Path(image_path).is_file()]

    if missing_paths:
        for missing_path in missing_paths:
            print(f"Error: Image file not found: {missing_path}")
        return

    if DeepFace is None:
        print("Error: DeepFace or one of its model dependencies could not be initialized.")
        print(f"Details: {DEEPFACE_IMPORT_ERROR}")
        return

    try:
        result: dict[str, Any] = DeepFace.verify(
            img1_path=reference_image_path,
            img2_path=captured_image_path,
            model_name="ArcFace",
            detector_backend="retinaface",
            distance_metric="cosine",
            align=True,
            enforce_detection=True,
        )
    except FileNotFoundError as error:
        # This also covers files removed after the checks above.
        missing_path = error.filename or str(error)
        print(f"Error: Image file not found: {missing_path}")
        return
    except ValueError as error:
        # DeepFace commonly uses ValueError for detection and invalid-image errors.
        print(f"Error: {_describe_value_error(error)}")
        return
    except (ImportError, ModuleNotFoundError, OSError, RuntimeError) as error:
        print("Error: DeepFace, ArcFace, RetinaFace, or a required model dependency failed to initialize.")
        print(f"Details: {error}")
        return
    except Exception as error:
        print(f"Error: An unexpected verification error occurred: {error}")
        return

    verified = bool(result.get("verified", False))

    print("\nFace Verification Summary")
    print("-------------------------")
    print(f"Verified: {verified}")
    print(f"Distance: {result.get('distance', 'Not returned')}")
    print(f"Threshold: {result.get('threshold', 'Not returned')}")
    print(f"Recognition model: {result.get('model', MODEL_NAME)}")
    print(f"Detector backend: {DETECTOR_BACKEND}")
    print(f"Similarity metric: {result.get('similarity_metric', DISTANCE_METRIC)}")

    if "time" in result:
        print(f"Total verification time: {result['time']} seconds")

    if verified:
        print("Result: The two images appear to belong to the same person.")
    else:
        print("Result: The two images do not appear to belong to the same person.")

    print("\nRaw DeepFace result:")
    print(result)


# This test generates embeddings for both images on every run, so it is only
# suitable for initial testing. A future enrolment workflow will generate and
# store the reference embedding once; attendance will generate only the captured
# image embedding before comparing it with the stored reference embedding.
if __name__ == "__main__":
    verify_faces(REFERENCE_IMAGE_PATH, CAPTURED_IMAGE_PATH)
