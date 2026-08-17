import argparse
import asyncio
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from adapters.insightface_engine import create_configured_insightface_engine
from core.config import get_settings
from db.engine import create_database_engine, dispose_database_engine
from db.session import create_session_factory
from repositories.student_profile_repository import StudentProfileRepository
from services.reference_enrollment_service import (
    ReferenceEnrollmentService,
    ReferenceEnrollmentStatus,
)


SUPPORTED_IMAGE_EXTENSIONS = frozenset(
    {
        ".jpeg",
        ".jpg",
        ".png",
    }
)


@dataclass(slots=True)
class ImportSummary:
    discovered: int = 0
    enrolled: int = 0
    already_enrolled: int = 0
    validated: int = 0
    skipped: int = 0
    failed: int = 0

# Return supported image files directly inside the supplied directory.
def discover_reference_photos(directory: Path) -> list[Path]:

    if not directory.exists():
        raise ValueError(f"Photo directory does not exist: {directory}")

    if not directory.is_dir():
        raise ValueError(f"Photo path is not a directory: {directory}")

    return sorted(
        (path for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS),
        key=lambda path: path.name.casefold(),
    )

# Use the filename without its extension as the registration number.
def registration_number_from_photo(photo_path: Path) -> str:

    registration_number = photo_path.stem.strip()

    if not registration_number:
        raise ValueError("Photo filename must contain a registration number")

    return registration_number

# Find students represented by more than one file in the same batch.
def find_duplicate_registration_numbers(photos: Sequence[Path],) -> set[str]:

    registration_numbers = [registration_number_from_photo(photo).casefold()for photo in photos]
    counts = Counter(registration_numbers)

    return {
        registration_number for registration_number, count in counts.items() if count > 1
    }

# Validate a photo batch and optionally store reference embeddings.
async def import_reference_photos(*, photos_directory: Path,commit: bool,) -> ImportSummary:

    photos = discover_reference_photos(photos_directory)
    summary = ImportSummary(discovered=len(photos))

    if not photos:
        print("No supported JPEG or PNG photographs were found.")
        return summary

    duplicate_registration_numbers = find_duplicate_registration_numbers(photos)

    settings = get_settings()
    database_engine = create_database_engine(settings)
    session_factory = create_session_factory(database_engine)

    # Dry-run mode validates filenames and database identities without loading
    # the large face model or writing any face-profile data.
    face_engine = None
    if commit:
        face_engine = create_configured_insightface_engine(settings)

    try:
        for photo_path in photos:
            registration_number = registration_number_from_photo(photo_path)

            if registration_number.casefold() in (duplicate_registration_numbers):
                print(f"[SKIPPED] {registration_number}: ""more than one photo has this registration number")
                summary.skipped += 1
                continue

            async with session_factory() as session:
                student_repository = StudentProfileRepository(session)
                student = await (student_repository.get_by_registration_number(registration_number))

                if student is None:
                    print(f"[FAILED] {registration_number}: ""student profile was not found")
                    summary.failed += 1
                    continue

                if (student.profile_status or "").casefold() != "active":
                    print(f"[SKIPPED] {registration_number}: ""student profile is not active")
                    summary.skipped += 1
                    continue

                if not commit:
                    print(f"[VALID] {registration_number}: ""active student profile found")
                    summary.validated += 1
                    continue

                if face_engine is None:
                    raise RuntimeError("Face engine was not created for commit mode")

                try:
                    photo_bytes = photo_path.read_bytes()
                    enrollment_service = ReferenceEnrollmentService(
                        session=session,
                        face_engine=face_engine,
                        model_version=settings.face_model_version,
                    )
                    result = await enrollment_service.enroll(student_id=student.id,official_photo=photo_bytes,)

                except Exception as error:
                    # Keep processing other students, but do not reveal image,
                    # embedding, or database secret values in the output.
                    print(f"[FAILED] {registration_number}: "f"{type(error).__name__}")
                    summary.failed += 1
                    continue

                if result.status is ReferenceEnrollmentStatus.SUCCESS:
                    confidence = result.detection_confidence
                    confidence_text = (f"{confidence:.4f}" if confidence is not None else "unknown")
                    print(
                        f"[ENROLLED] {registration_number}: "
                        f"model={result.model_name}, "
                        f"confidence={confidence_text}"
                    )
                    summary.enrolled += 1

                elif result.status is (ReferenceEnrollmentStatus.ALREADY_ENROLLED):
                    print(f"[UNCHANGED] {registration_number}: already enrolled")
                    summary.already_enrolled += 1

                elif result.status is (ReferenceEnrollmentStatus.PROFILE_REVOKED):
                    print(f"[SKIPPED] {registration_number}: profile is revoked")
                    summary.skipped += 1

                else:
                    print(f"[FAILED] {registration_number}: "f"{result.status.value}")
                    summary.failed += 1
    finally:
        await dispose_database_engine(database_engine)

    return summary


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Enroll reference faces from photographs named with student registration numbers. The default mode performs no writes.")
    )
    parser.add_argument("photos_directory",type=Path,help="Directory containing files such as 230XXX.png",)

    parser.add_argument("--commit",action="store_true",help="Generate and store embeddings; without this flag, dry-run only",)
    return parser


def print_summary(summary: ImportSummary, *, commit: bool) -> None:
    mode = "COMMIT" if commit else "DRY RUN"
    print()
    print(f"Reference enrollment summary ({mode})")
    print(f"  Discovered:       {summary.discovered}")
    print(f"  Validated:        {summary.validated}")
    print(f"  Enrolled:         {summary.enrolled}")
    print(f"  Already enrolled: {summary.already_enrolled}")
    print(f"  Skipped:          {summary.skipped}")
    print(f"  Failed:           {summary.failed}")


def main() -> int:
    parser = build_argument_parser()
    arguments = parser.parse_args()

    try:
        summary = asyncio.run(import_reference_photos(
                photos_directory=arguments.photos_directory.resolve(),
                commit=arguments.commit,
            )
        )
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"Enrollment import failed: {error}\n")

    print_summary(summary, commit=arguments.commit)

    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
