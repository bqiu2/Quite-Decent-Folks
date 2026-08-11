from __future__ import annotations

from plant_ai.prototype_classifier import get_type_classifier


def main() -> None:
    classifier = get_type_classifier()
    counts = classifier.reference_counts()
    print(f"Current reference counts: {counts}")
    classifier.rebuild_cache(force=True)
    print("Reference prototype cache rebuilt successfully.")


if __name__ == "__main__":
    main()
