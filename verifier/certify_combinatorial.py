from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "n19"
DEFAULT_OMATRIX_PATH = DEFAULT_DATA_DIR / "omatrix.json"
DEFAULT_CERTIFICATE_PATH = DEFAULT_DATA_DIR / "combinatorial_certificate.json"


def load_omatrix(path: Path) -> list[list[int]]:
    with path.open(encoding="utf-8") as handle:
        matrix = json.load(handle)

    if not isinstance(matrix, list) or len(matrix) != 19:
        raise ValueError(f"{path} must be a JSON array with 19 rows")

    for i, row in enumerate(matrix):
        if not isinstance(row, list) or len(row) != 18:
            raise ValueError(f"{path} row {i} must be a list of length 18")
        expected = set(range(19))
        expected.remove(i)
        if set(row) != expected:
            raise ValueError(f"{path} row {i} must contain each index except {i} exactly once")
        if len(set(row)) != 18:
            raise ValueError(f"{path} row {i} contains duplicate indices")

    return matrix


def compute_file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def is_triangle(omatrix: list[list[int]], a: int, b: int, c: int) -> bool:
    for line_index, first, second in ((a, b, c), (b, a, c), (c, a, b)):
        row = omatrix[line_index]
        if abs(row.index(first) - row.index(second)) != 1:
            return False
    return True


def count_bounded_triangles(omatrix: list[list[int]]) -> tuple[int, list[tuple[int, int, int]]]:
    triangles: list[tuple[int, int, int]] = []
    n = len(omatrix)
    for a in range(n):
        for b in range(a + 1, n):
            for c in range(b + 1, n):
                if is_triangle(omatrix, a, b, c):
                    triangles.append((a, b, c))
    return len(triangles), triangles


def touching_segments_on_y0(omatrix: list[list[int]]) -> tuple[int, list[tuple[int, int]]]:
    row = omatrix[0]
    touched: list[tuple[int, int]] = []
    for left, right in zip(row, row[1:]):
        if is_triangle(omatrix, 0, left, right):
            touched.append((left, right))
    return len(touched), touched


def segment_endpoints(line_index: int, left: int, right: int) -> tuple[tuple[int, int], tuple[int, int]]:
    return tuple(sorted((line_index, left))), tuple(sorted((line_index, right)))


def serialize_segment(line_index: int, left: int, right: int) -> dict:
    start, end = segment_endpoints(line_index, left, right)
    return {
        "line": line_index,
        "between": [left, right],
        "endpoints": [list(start), list(end)],
    }


def collect_unused_segments(omatrix: list[list[int]]) -> list[dict]:
    unused_segments: list[dict] = []
    for line_index, row in enumerate(omatrix):
        for left, right in zip(row, row[1:]):
            if not is_triangle(omatrix, line_index, left, right):
                unused_segments.append(serialize_segment(line_index, left, right))
    unused_segments.sort(key=lambda segment: (segment["line"], segment["between"][0], segment["between"][1]))
    return unused_segments


def build_certificate(omatrix_path: Path) -> dict:
    omatrix = load_omatrix(omatrix_path)

    touching_segments, touched_pairs = touching_segments_on_y0(omatrix)
    touching_condition_on_y0 = touching_segments == 17

    bounded_triangles, triangles = count_bounded_triangles(omatrix)
    unused_segments = collect_unused_segments(omatrix)
    unused_segments_count = len(unused_segments)
    has_2_unused_segments = unused_segments_count == 2
    has_107_bounded_triangles = bounded_triangles == 107

    verdict = (
        touching_condition_on_y0
        and has_2_unused_segments
        and has_107_bounded_triangles
    )

    return {
        "n": len(omatrix),
        "omatrix_checksum": compute_file_checksum(omatrix_path),
        "touching_segments": touching_segments,
        "touching_condition_on_Y0": touching_condition_on_y0,
        "bounded_triangles": bounded_triangles,
        "has_107_bounded_triangles": has_107_bounded_triangles,
        "unused_segments_count": unused_segments_count,
        "has_2_unused_segments": has_2_unused_segments,
        "unused_segments": unused_segments,
        "verdict": verdict,
        "diagnostics": {
            "omatrix_row_0": omatrix[0],
            "touched_pairs_on_y0": touched_pairs,
            "triangles_sample": triangles[:10],
        },
    }


def write_certificate(certificate: dict, path: Path) -> None:
    path.write_text(json.dumps(certificate, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run combinatorial structural verification for the public seed n=19 O-matrix.")
    parser.add_argument("--omatrix", type=Path, default=DEFAULT_OMATRIX_PATH, help="Path to omatrix.json")
    parser.add_argument(
        "--certificate",
        type=Path,
        default=DEFAULT_CERTIFICATE_PATH,
        help="Where to write combinatorial_certificate.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    certificate = build_certificate(omatrix_path=args.omatrix)
    write_certificate(certificate, args.certificate)
    print(json.dumps(certificate, indent=2, ensure_ascii=True))
    return 0 if certificate["verdict"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
