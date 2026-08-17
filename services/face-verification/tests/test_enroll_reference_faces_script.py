from pathlib import Path

import pytest

from scripts.enroll_reference_faces import (
    discover_reference_photos,
    find_duplicate_registration_numbers,
    registration_number_from_photo,
)


def test_uses_photo_filename_as_registration_number() -> None:
    photo = Path("230734J.png")

    assert registration_number_from_photo(photo) == "230734J"


def test_discovers_only_supported_images_in_top_level_directory(
    tmp_path: Path,
) -> None:
    (tmp_path / "230734J.png").touch()
    (tmp_path / "230735K.JPG").touch()
    (tmp_path / "notes.txt").touch()
    nested_directory = tmp_path / "nested"
    nested_directory.mkdir()
    (nested_directory / "230736L.png").touch()

    photos = discover_reference_photos(tmp_path)

    assert [photo.name for photo in photos] == [
        "230734J.png",
        "230735K.JPG",
    ]


def test_detects_duplicate_registration_numbers_case_insensitively() -> None:
    photos = [
        Path("230734J.png"),
        Path("230734j.jpg"),
        Path("230735K.png"),
    ]

    duplicates = find_duplicate_registration_numbers(photos)

    assert duplicates == {"230734j"}


def test_rejects_missing_photo_directory(tmp_path: Path) -> None:
    missing_directory = tmp_path / "missing"

    with pytest.raises(ValueError, match="Photo directory does not exist"):
        discover_reference_photos(missing_directory)
