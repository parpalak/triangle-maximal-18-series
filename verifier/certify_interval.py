from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "n19"
DEFAULT_LINES_PATH = DEFAULT_DATA_DIR / "lines.csv"
DEFAULT_OMATRIX_PATH = DEFAULT_DATA_DIR / "omatrix.json"
DEFAULT_INTERVAL_CERTIFICATE_PATH = DEFAULT_DATA_DIR / "interval_certificate.json"

EXPECTED_ROW0_LABELS = [
    "-tan(8pi/18)",
    "-tan(7pi/18)",
    "-tan(6pi/18)",
    "-tan(5pi/18)",
    "-tan(4pi/18)",
    "-tan(3pi/18)",
    "-tan(2pi/18)",
    "-tan(1pi/18)",
    "-epsilon",
    "+epsilon",
    "+tan(1pi/18)",
    "+tan(2pi/18)",
    "+tan(3pi/18)",
    "+tan(4pi/18)",
    "+tan(5pi/18)",
    "+tan(6pi/18)",
    "+tan(7pi/18)",
    "+tan(8pi/18)",
]
RECOGNITION_TOLERANCE = 1e-10
EPSILON_INTERVAL_LO = Fraction(1, 10**12)
TAN18_NUMERATOR_COEFFICIENTS = [
    0,
    18,
    0,
    -816,
    0,
    8568,
    0,
    -31824,
    0,
    48620,
    0,
    -31824,
    0,
    8568,
    0,
    -816,
    0,
    18,
]


@dataclass(frozen=True)
class Line:
    m: Fraction
    b: Fraction
    m_raw: str
    b_raw: str


@dataclass(frozen=True)
class Interval:
    lo: Fraction
    hi: Fraction

    def __post_init__(self) -> None:
        if self.lo > self.hi:
            raise ValueError(f"invalid interval [{self.lo}, {self.hi}]")


def parse_fraction(value: str) -> Fraction:
    return Fraction(value.strip())


def fraction_to_decimal(value: Fraction, digits: int = 18) -> str:
    return format(float(value), f".{digits}g")


def load_lines(path: Path) -> list[Line]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["m", "b"]:
            raise ValueError(f"{path} must have CSV header ['m', 'b'], got {reader.fieldnames!r}")

        lines = [
            Line(
                m=parse_fraction(row["m"]),
                b=parse_fraction(row["b"]),
                m_raw=row["m"].strip(),
                b_raw=row["b"].strip(),
            )
            for row in reader
        ]

    if len(lines) != 19:
        raise ValueError(f"{path} must contain exactly 19 lines, got {len(lines)}")
    if (lines[0].m, lines[0].b) != (Fraction(0), Fraction(0)):
        raise ValueError(f"{path} must start with Y_0 = y = 0, got {(lines[0].m, lines[0].b)!r}")

    return lines


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


def compute_input_checksum(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def compute_file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def affine_anchor(line: Line) -> Fraction:
    if line.m == 0:
        return Fraction(0)
    return -line.b / line.m


def point_interval(value: Fraction) -> Interval:
    return Interval(value, value)


def interval_add(left: Interval, right: Interval) -> Interval:
    return Interval(left.lo + right.lo, left.hi + right.hi)


def interval_sub(left: Interval, right: Interval) -> Interval:
    return Interval(left.lo - right.hi, left.hi - right.lo)


def interval_mul(left: Interval, right: Interval) -> Interval:
    products = [
        left.lo * right.lo,
        left.lo * right.hi,
        left.hi * right.lo,
        left.hi * right.hi,
    ]
    return Interval(min(products), max(products))


def interval_div(left: Interval, right: Interval) -> Interval:
    if right.lo <= 0 <= right.hi:
        raise ValueError(f"division by interval containing 0: {right}")
    reciprocals = [Fraction(1, 1) / right.lo, Fraction(1, 1) / right.hi]
    return interval_mul(left, Interval(min(reciprocals), max(reciprocals)))


def interval_contains(interval: Interval, value: Fraction) -> bool:
    return interval.lo <= value <= interval.hi


def expand_interval(interval: Interval, radius: Fraction) -> Interval:
    return Interval(interval.lo - radius, interval.hi + radius)


def parse_label_index(label: str) -> int:
    return int(label.split("(")[1].split("pi")[0])


def evaluate_polynomial(coefficients: list[int], x: Fraction) -> Fraction:
    value = Fraction(0)
    for coefficient in reversed(coefficients):
        value = value * x + coefficient
    return value


@lru_cache(maxsize=None)
def certify_positive_tan_interval(k: int) -> Interval:
    center = math.tan(k * math.pi / 18.0)
    radius = 1e-6
    for _ in range(32):
        lo = Fraction(str(center - radius))
        hi = Fraction(str(center + radius))
        value_lo = evaluate_polynomial(TAN18_NUMERATOR_COEFFICIENTS, lo)
        value_hi = evaluate_polynomial(TAN18_NUMERATOR_COEFFICIENTS, hi)
        if value_lo == 0:
            lo -= Fraction(1, 10**12)
            value_lo = evaluate_polynomial(TAN18_NUMERATOR_COEFFICIENTS, lo)
        if value_hi == 0:
            hi += Fraction(1, 10**12)
            value_hi = evaluate_polynomial(TAN18_NUMERATOR_COEFFICIENTS, hi)
        if value_lo * value_hi < 0:
            return Interval(lo, hi)
        radius /= 2
    raise ValueError(f"failed to certify tan({k}pi/18) interval")


def prettify_radius_down(radius: Fraction) -> Fraction:
    if radius <= 0:
        raise ValueError(f"radius must be positive, got {radius}")

    exponent = math.floor(math.log10(float(radius)))
    while True:
        base = Fraction(10) ** exponent
        for multiplier in (5, 2, 1):
            candidate = multiplier * base
            if candidate <= radius:
                return candidate
        exponent -= 1


def prettify_positive_bound_down(value: Fraction) -> Fraction:
    if value <= 0:
        raise ValueError(f"value must be positive, got {value}")
    return prettify_radius_down(value)


def prettify_positive_bound_up(value: Fraction) -> Fraction:
    if value <= 0:
        raise ValueError(f"value must be positive, got {value}")

    exponent = math.floor(math.log10(float(value)))
    while True:
        base = Fraction(10) ** exponent
        for multiplier in (1, 2, 5):
            candidate = multiplier * base
            if candidate >= value:
                return candidate
        exponent += 1


def expected_label_value(label: str, epsilon: Fraction) -> float:
    if label == "-epsilon":
        return -float(epsilon)
    if label == "+epsilon":
        return float(epsilon)

    sign = -1.0 if label.startswith("-") else 1.0
    k = int(label.split("(")[1].split("pi")[0])
    return sign * math.tan(k * math.pi / 18.0)


def exact_label_interval(label: str, epsilon_interval: Interval) -> Interval:
    if label == "-epsilon":
        return Interval(-epsilon_interval.hi, -epsilon_interval.lo)
    if label == "+epsilon":
        return Interval(epsilon_interval.lo, epsilon_interval.hi)

    tan_interval = certify_positive_tan_interval(parse_label_index(label))
    if label.startswith("-"):
        return Interval(-tan_interval.hi, -tan_interval.lo)
    return tan_interval


def recognize_normalization(lines: list[Line], omatrix: list[list[int]]) -> tuple[dict[int, str], Fraction, list[str]]:
    row0 = omatrix[0]
    actual_anchors = {line_index: affine_anchor(lines[line_index]) for line_index in row0}

    negative_epsilon_line = row0[8]
    positive_epsilon_line = row0[9]
    epsilon = (abs(actual_anchors[negative_epsilon_line]) + abs(actual_anchors[positive_epsilon_line])) / 2

    if epsilon <= 0:
        raise ValueError("failed to recover positive epsilon from row 0")

    label_by_line = {line_index: label for line_index, label in zip(row0, EXPECTED_ROW0_LABELS)}

    mismatches: list[str] = []
    for line_index, label in label_by_line.items():
        actual_anchor = actual_anchors[line_index]
        padded_interval = expand_interval(
            exact_label_interval(label, point_interval(epsilon)),
            Fraction.from_float(RECOGNITION_TOLERANCE),
        )
        if not interval_contains(padded_interval, actual_anchor):
            actual = float(actual_anchor)
            expected = expected_label_value(label, epsilon)
            mismatches.append(
                f"line {line_index}: expected {label} ~= {expected:.16g}, got {actual:.16g}"
            )

    return label_by_line, epsilon, mismatches


def y_coordinate(lines: list[Line], i: int, j: int) -> Fraction:
    line_i = lines[i]
    line_j = lines[j]

    if i == 0 or j == 0:
        denominator = line_i.m - line_j.m
        if denominator == 0:
            raise ValueError(f"lines {i} and {j} are parallel")
        x = (line_j.b - line_i.b) / denominator
        return line_i.m * x + line_i.b

    a_i = affine_anchor(line_i)
    a_j = affine_anchor(line_j)
    denominator = line_i.m - line_j.m
    if denominator == 0:
        raise ValueError(f"lines {i} and {j} are parallel")
    return line_i.m * line_j.m * (a_i - a_j) / denominator


def build_a_intervals(
    lines: list[Line], label_by_line: dict[int, str], epsilon_interval: Interval
) -> dict[int, Interval]:
    intervals = {0: point_interval(Fraction(0))}
    for line_index in range(1, len(lines)):
        intervals[line_index] = exact_label_interval(label_by_line[line_index], epsilon_interval)
    return intervals


def interval_y_coordinate(
    i: int,
    j: int,
    m_intervals: dict[int, Interval],
    a_intervals: dict[int, Interval],
) -> Interval:
    if j == 0:
        return point_interval(Fraction(0))

    m_i = m_intervals[i]
    m_j = m_intervals[j]
    a_diff = interval_sub(a_intervals[i], a_intervals[j])
    numerator = interval_mul(interval_mul(m_i, m_j), a_diff)
    denominator = interval_sub(m_i, m_j)
    return interval_div(numerator, denominator)


def interval_y_difference(
    i: int,
    left: int,
    right: int,
    m_intervals: dict[int, Interval],
    a_intervals: dict[int, Interval],
) -> Interval:
    return interval_sub(
        interval_y_coordinate(i, left, m_intervals, a_intervals),
        interval_y_coordinate(i, right, m_intervals, a_intervals),
    )


def verify_row_orders(lines: list[Line], omatrix: list[list[int]]) -> tuple[bool, int, Fraction, list[dict]]:
    checked_rows = []
    min_margin: Fraction | None = None
    inequalities_count = 0
    all_rows_ok = True

    for i in range(1, len(omatrix)):
        row = omatrix[i]
        y_values = [y_coordinate(lines, i, j) for j in row]
        row_margins = [left - right for left, right in zip(y_values, y_values[1:])]
        row_ok = all(margin > 0 for margin in row_margins)
        all_rows_ok = all_rows_ok and row_ok
        inequalities_count += len(row_margins)
        row_min_margin = min(row_margins)

        if min_margin is None or row_min_margin < min_margin:
            min_margin = row_min_margin

        checked_rows.append(
            {
                "row": i,
                "ok": row_ok,
                "min_margin": str(row_min_margin),
            }
        )

    if min_margin is None:
        raise ValueError("no row inequalities were checked")

    return all_rows_ok, inequalities_count, min_margin, checked_rows


def parallel_separation_margin(lines: list[Line]) -> Fraction:
    min_margin: Fraction | None = None
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            margin = abs(lines[i].m - lines[j].m)
            if min_margin is None or margin < min_margin:
                min_margin = margin
    if min_margin is None:
        raise ValueError("failed to compute parallel separation margin")
    return min_margin


def interval_parallel_separation_margin(m_intervals: dict[int, Interval]) -> Fraction:
    min_margin: Fraction | None = None
    for i in range(len(m_intervals)):
        for j in range(i + 1, len(m_intervals)):
            diff = interval_sub(m_intervals[i], m_intervals[j])
            if diff.lo > 0:
                margin = diff.lo
            elif diff.hi < 0:
                margin = -diff.hi
            else:
                return Fraction(0)
            if min_margin is None or margin < min_margin:
                min_margin = margin
    if min_margin is None:
        raise ValueError("failed to compute interval parallel separation margin")
    return min_margin


def verify_row_orders_interval(
    omatrix: list[list[int]],
    m_intervals: dict[int, Interval],
    a_intervals: dict[int, Interval],
) -> tuple[bool, int, Fraction, list[dict]]:
    checked_rows = []
    min_margin: Fraction | None = None
    inequalities_count = 0
    all_rows_ok = True

    for i in range(1, len(omatrix)):
        row = omatrix[i]
        row_margins = [
            interval_y_difference(i, left, right, m_intervals, a_intervals).lo
            for left, right in zip(row, row[1:])
        ]
        row_ok = all(margin > 0 for margin in row_margins)
        all_rows_ok = all_rows_ok and row_ok
        inequalities_count += len(row_margins)
        row_min_margin = min(row_margins)

        if min_margin is None or row_min_margin < min_margin:
            min_margin = row_min_margin

        checked_rows.append(
            {
                "row": i,
                "ok": row_ok,
                "min_margin": str(row_min_margin),
            }
        )

    if min_margin is None:
        raise ValueError("no interval row inequalities were checked")

    return all_rows_ok, inequalities_count, min_margin, checked_rows


def verify_direction_order_at_infinity(
    row0: list[int], label_by_line: dict[int, str], m_intervals: dict[int, Interval]
) -> dict:
    ordered_labels = [label_by_line[line_index] for line_index in row0]
    ordered_lines = list(range(1, len(m_intervals)))
    failures = []
    min_margin: Fraction | None = None

    if ordered_labels != EXPECTED_ROW0_LABELS:
        failures.append(
            {
                "kind": "row0_label_order",
                "expected": EXPECTED_ROW0_LABELS,
                "actual": ordered_labels,
            }
        )

    negative_block = []
    positive_block = []
    pole_crossing_index: int | None = None
    seen_positive = False
    for line_index in ordered_lines:
        interval = m_intervals[line_index]
        negative_margin = -interval.hi
        positive_margin = interval.lo
        if negative_margin > 0:
            if seen_positive:
                failures.append(
                    {
                        "kind": "multiple_tan_pole_crossings",
                        "line": line_index,
                        "interval": [str(interval.lo), str(interval.hi)],
                    }
                )
            negative_block.append(line_index)
            if min_margin is None or negative_margin < min_margin:
                min_margin = negative_margin
        elif positive_margin > 0:
            if pole_crossing_index is None:
                pole_crossing_index = line_index
            seen_positive = True
            positive_block.append(line_index)
            if min_margin is None or positive_margin < min_margin:
                min_margin = positive_margin
        else:
            failures.append(
                {
                    "kind": "sign_ambiguous",
                    "line": line_index,
                    "interval": [str(interval.lo), str(interval.hi)],
                }
            )
            margin = max(negative_margin, positive_margin)
            if min_margin is None or margin < min_margin:
                min_margin = margin

    if not negative_block or not positive_block:
        failures.append(
            {
                "kind": "missing_tan_pole_crossing",
                "negative_block_lines": negative_block,
                "positive_block_lines": positive_block,
            }
        )
    else:
        pole_crossing_margin = min(-m_intervals[negative_block[-1]].hi, m_intervals[positive_block[0]].lo)
        if min_margin is None or pole_crossing_margin < min_margin:
            min_margin = pole_crossing_margin

    for left, right in zip(negative_block, negative_block[1:]):
        margin = m_intervals[left].lo - m_intervals[right].hi
        if margin <= 0:
            failures.append(
                {
                    "kind": "negative_block_order",
                    "left": left,
                    "right": right,
                    "left_interval": [str(m_intervals[left].lo), str(m_intervals[left].hi)],
                    "right_interval": [str(m_intervals[right].lo), str(m_intervals[right].hi)],
                }
            )
        if min_margin is None or margin < min_margin:
            min_margin = margin

    for left, right in zip(positive_block, positive_block[1:]):
        margin = m_intervals[left].lo - m_intervals[right].hi
        if margin <= 0:
            failures.append(
                {
                    "kind": "positive_block_order",
                    "left": left,
                    "right": right,
                    "left_interval": [str(m_intervals[left].lo), str(m_intervals[left].hi)],
                    "right_interval": [str(m_intervals[right].lo), str(m_intervals[right].hi)],
                }
            )
        if min_margin is None or margin < min_margin:
            min_margin = margin

    if min_margin is None:
        raise ValueError("failed to verify direction order at infinity")

    return {
        "ok": not failures,
        "rule": "the sequence (m_1,...,m_n) crosses the pole of tan at pi/2 exactly once: a negative descending block followed by a positive descending block",
        "row0_labels": ordered_labels,
        "ordered_lines": ordered_lines,
        "negative_block_lines": negative_block,
        "positive_block_lines": positive_block,
        "pole_crossing_line": pole_crossing_index,
        "min_margin": str(min_margin),
        "failures": failures,
    }


def verify_epsilon_zero_limit(
    lines: list[Line],
    omatrix: list[list[int]],
    label_by_line: dict[int, str],
    special_lines: list[int],
    certified_m_intervals: dict[int, Interval] | None = None,
) -> dict:
    if certified_m_intervals is not None:
        m_intervals = certified_m_intervals
    else:
        m_intervals = {0: point_interval(Fraction(0))}
        for line_index in range(1, len(lines)):
            m_intervals[line_index] = point_interval(lines[line_index].m)
    a_intervals = build_a_intervals(lines, label_by_line, point_interval(Fraction(0)))

    zero_inequalities = []
    negative_inequalities = []
    for i in range(1, len(omatrix)):
        row = omatrix[i]
        for position, (left, right) in enumerate(zip(row, row[1:]), start=1):
            diff = interval_y_difference(i, left, right, m_intervals, a_intervals)
            if diff.lo == 0 and diff.hi == 0:
                zero_inequalities.append(
                    {
                        "row": i,
                        "position": position,
                        "left": left,
                        "right": right,
                    }
                )
            elif diff.hi < 0:
                negative_inequalities.append(
                    {
                        "row": i,
                        "position": position,
                        "left": left,
                        "right": right,
                    }
                )

    actual_zero_inequalities = sorted(zero_inequalities, key=lambda item: (item["row"], item["position"]))
    required_zero_inequalities_count = 2

    return {
        "ok": not negative_inequalities and len(actual_zero_inequalities) == required_zero_inequalities_count,
        "zero_inequalities": actual_zero_inequalities,
        "zero_inequalities_count": len(actual_zero_inequalities),
        "negative_inequalities": negative_inequalities,
        "negative_inequalities_count": len(negative_inequalities),
        "required_zero_inequalities_count": required_zero_inequalities_count,
        "special_lines": special_lines,
    }


def build_positive_intervals(
    lines: list[Line],
    omatrix: list[list[int]],
    label_by_line: dict[int, str],
    epsilon: Fraction,
) -> tuple[dict[int, Interval], Interval, Fraction, Fraction, list[dict], int]:
    def try_radius(radius: Fraction) -> tuple[bool, dict[int, Interval], Fraction, list[dict], int, Fraction]:
        m_intervals = {0: point_interval(Fraction(0))}
        for line_index in range(1, len(lines)):
            m_intervals[line_index] = Interval(lines[line_index].m - radius, lines[line_index].m + radius)

        a_intervals = build_a_intervals(lines, label_by_line, epsilon_interval)
        try:
            row_orders_ok, inequalities_count, row_margin, checked_rows = verify_row_orders_interval(
                omatrix, m_intervals, a_intervals
            )
            parallel_margin = interval_parallel_separation_margin(m_intervals)
        except ValueError:
            return False, m_intervals, Fraction(0), [], 0, Fraction(0)

        if not row_orders_ok or parallel_margin <= 0:
            return False, m_intervals, row_margin, checked_rows, inequalities_count, parallel_margin

        return True, m_intervals, row_margin, checked_rows, inequalities_count, parallel_margin

    point_parallel_margin = parallel_separation_margin(lines)
    epsilon_interval_hi = prettify_positive_bound_up(epsilon)
    if epsilon_interval_hi < EPSILON_INTERVAL_LO:
        raise ValueError(
            f"recovered epsilon upper bound {epsilon_interval_hi} is smaller than lower bound {EPSILON_INTERVAL_LO}"
        )
    epsilon_interval = Interval(EPSILON_INTERVAL_LO, epsilon_interval_hi)
    radius = point_parallel_margin / 8
    if radius <= 0:
        raise ValueError("failed to construct a positive initial interval radius")

    certified_radius: Fraction | None = None
    for _ in range(64):
        ok, m_intervals, row_margin, checked_rows, inequalities_count, parallel_margin = try_radius(radius)
        if ok:
            certified_radius = radius
            break

        radius /= 2

    if certified_radius is None:
        raise ValueError("failed to certify a positive interval box for n=19 seed")

    lower = certified_radius
    upper = point_parallel_margin / 2
    if upper <= lower:
        upper = lower

    for _ in range(80):
        mid = (lower + upper) / 2
        ok, _, _, _, _, _ = try_radius(mid)
        if ok:
            lower = mid
        else:
            upper = mid

    final_ok, final_m_intervals, final_row_margin, final_checked_rows, final_inequalities_count, final_parallel_margin = try_radius(
        lower
    )
    if not final_ok:
        raise ValueError(f"binary-searched radius {lower} failed unexpectedly")

    return (
        final_m_intervals,
        epsilon_interval,
        final_row_margin,
        final_parallel_margin,
        final_checked_rows,
        final_inequalities_count,
    )

    


def build_interval_certificate(lines_path: Path, omatrix_path: Path) -> dict:
    lines = load_lines(lines_path)
    omatrix = load_omatrix(omatrix_path)

    label_by_line, epsilon, normalization_mismatches = recognize_normalization(lines, omatrix)
    (
        certified_m_intervals,
        epsilon_interval,
        row_order_min_margin,
        parallel_margin,
        checked_rows,
        inequalities_count,
    ) = build_positive_intervals(lines, omatrix, label_by_line, epsilon)

    special_lines = sorted(
        line_index
        for line_index, label in label_by_line.items()
        if label in {"-epsilon", "+epsilon"}
    )
    epsilon_zero_limit = verify_epsilon_zero_limit(lines, omatrix, label_by_line, special_lines, certified_m_intervals)
    row_orders_ok = all(row["ok"] for row in checked_rows)
    direction_order_at_infinity = verify_direction_order_at_infinity(omatrix[0], label_by_line, certified_m_intervals)
    omatrix_realized_by_bbl = row_orders_ok and not normalization_mismatches
    verdict = (
        omatrix_realized_by_bbl
        and parallel_margin > 0
        and direction_order_at_infinity["ok"]
        and epsilon_zero_limit["ok"]
    )

    a_values = [
        {
            "line": line_index,
            "label": label_by_line[line_index],
            "recovered_from_input": fraction_to_decimal(affine_anchor(lines[line_index])),
        }
        for line_index in range(1, len(lines))
    ]

    m_values = [
        {
            "line": line_index,
            "recovered_from_input": lines[line_index].m_raw,
        }
        for line_index in range(1, len(lines))
    ]

    m_intervals = [
        {
            "line": line_index,
            "interval": [
                str(certified_m_intervals[line_index].lo),
                str(certified_m_intervals[line_index].hi),
            ],
        }
        for line_index in range(1, len(lines))
    ]

    return {
        "n": len(lines),
        "input_checksum": compute_input_checksum([lines_path]),
        "omatrix_checksum": compute_file_checksum(omatrix_path),
        "normalization": {
            "y0_line": 0,
            "order_for_rows_1_to_18": "descending_y",
            "special_lines": special_lines,
            "interval_box_kind": "positive_rational_box",
        },
        "a_values": a_values,
        "m_values": m_values,
        "epsilon": {
            "recovered_from_input": fraction_to_decimal(epsilon),
            "interval": [str(epsilon_interval.lo), str(epsilon_interval.hi)],
        },
        "m_intervals": m_intervals,
        "checked_rows": [row["row"] for row in checked_rows],
        "row_order_inequalities_count": inequalities_count,
        "row_order_min_margin": str(row_order_min_margin),
        "parallel_separation_min_margin": str(parallel_margin),
        "direction_order_at_infinity_min_margin": direction_order_at_infinity["min_margin"],
        "omatrix_realized_by_bbl": omatrix_realized_by_bbl,
        "verdict": verdict,
        "diagnostics": {
            "checked_rows": checked_rows,
            "normalization_mismatches": normalization_mismatches,
            "direction_order_at_infinity": direction_order_at_infinity,
            "epsilon_zero_limit": epsilon_zero_limit,
            "row0_line_labels": [
                {"line": line_index, "label": label_by_line[line_index]}
                for line_index in omatrix[0]
            ],
        },
    }


def write_certificate(certificate: dict, path: Path) -> None:
    path.write_text(json.dumps(certificate, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize the public seed n=19 dataset and certify O-matrix order.")
    parser.add_argument("--lines", type=Path, default=DEFAULT_LINES_PATH, help="Path to lines.csv")
    parser.add_argument("--omatrix", type=Path, default=DEFAULT_OMATRIX_PATH, help="Path to omatrix.json")
    parser.add_argument(
        "--interval-certificate",
        type=Path,
        default=DEFAULT_INTERVAL_CERTIFICATE_PATH,
        help="Where to write interval_certificate.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    certificate = build_interval_certificate(args.lines, args.omatrix)
    write_certificate(certificate, args.interval_certificate)
    print(json.dumps(certificate, indent=2, ensure_ascii=True))
    return 0 if certificate["verdict"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
