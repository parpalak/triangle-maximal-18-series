#!/usr/bin/env python3
from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path


PREPRINT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = PREPRINT_DIR.parent
DATA_DIR = PROJECT_DIR / "data" / "n19"
GENERATED_DIR = PREPRINT_DIR / "generated"

INTERVAL_CERTIFICATE_PATH = DATA_DIR / "interval_certificate.json"
OMATRIX_PATH = DATA_DIR / "omatrix.json"

NORMALIZED_INCLUDE_PATH = GENERATED_DIR / "seed19_normalized_data.tex"
OMATRIX_INCLUDE_PATH = GENERATED_DIR / "seed19_omatrix.tex"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def tex_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return rf"\frac{{{value.numerator}}}{{{value.denominator}}}"


def decimal_string(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)

    numerator = abs(value.numerator)
    denominator = value.denominator
    power_of_two = 0
    power_of_five = 0

    while denominator % 2 == 0:
        denominator //= 2
        power_of_two += 1
    while denominator % 5 == 0:
        denominator //= 5
        power_of_five += 1

    if denominator != 1:
        raise ValueError(f"fraction {value} does not have a terminating decimal expansion")

    scale = max(power_of_two, power_of_five)
    scaled_numerator = numerator * (10**scale) // value.denominator
    digits = str(scaled_numerator).rjust(scale + 1, "0")
    integer_part = digits[:-scale] if scale else digits
    fractional_part = digits[-scale:] if scale else ""

    sign = "-" if value < 0 else ""
    if not fractional_part:
        return sign + integer_part
    return sign + integer_part + "." + fractional_part


def scientific_tex(value: Fraction) -> str:
    if value == 0:
        return "0"

    sign = "-" if value < 0 else ""
    decimal = decimal_string(abs(value))
    if "." in decimal:
        integer_part, fractional_part = decimal.split(".", 1)
    else:
        integer_part, fractional_part = decimal, ""

    if integer_part != "0":
        exponent = len(integer_part) - 1
        mantissa_digits = integer_part + fractional_part
        mantissa = mantissa_digits[0]
        tail = mantissa_digits[1:].rstrip("0")
    else:
        first_nonzero = next(i for i, ch in enumerate(fractional_part) if ch != "0")
        exponent = -(first_nonzero + 1)
        mantissa = fractional_part[first_nonzero]
        tail = fractional_part[first_nonzero + 1 :].rstrip("0")

    if tail:
        mantissa = mantissa + "." + tail
    if mantissa == "1":
        return rf"{sign}10^{{{exponent}}}"
    return rf"{sign}{mantissa}\cdot 10^{{{exponent}}}"


def round_fraction(value: Fraction, places: int) -> Fraction:
    decimal = Decimal(value.numerator) / Decimal(value.denominator)
    quantum = Decimal("1").scaleb(-places)
    return Fraction(str(decimal.quantize(quantum, rounding=ROUND_HALF_UP)))


def format_fraction_fixed_places(value: Fraction, places: int) -> str:
    decimal = Decimal(value.numerator) / Decimal(value.denominator)
    quantum = Decimal("1").scaleb(-places)
    return format(decimal.quantize(quantum, rounding=ROUND_HALF_UP), "f")


def _label_to_tex(label: str) -> str:
    """Convert a label like '+tan(8pi/18)' or '+epsilon' to LaTeX."""
    label = label.strip()
    if label in ("+epsilon", "-epsilon"):
        sign = "+" if label.startswith("+") else "-"
        return sign + r"\eps"
    sign = "+" if label.startswith("+") else "-"
    body = label.lstrip("+-")
    # body is like 'tan(8pi/18)'
    body = body.replace("pi", r"\pi")
    # tan(8\pi/18) -> \tan(8\pi/18)
    body = body.replace("tan(", r"\tan(")
    return sign + body


def render_normalized_data(certificate: dict) -> str:
    epsilon_lo, epsilon_hi = (Fraction(value) for value in certificate["epsilon"]["interval"])

    centers_by_line = {}
    radii = set()
    for item in certificate["m_intervals"]:
        lo, hi = (Fraction(value) for value in item["interval"])
        centers_by_line[item["line"]] = (lo + hi) / 2
        radii.add((hi - lo) / 2)

    if len(radii) != 1:
        raise ValueError(f"expected a common slope radius, got {sorted(radii)!r}")
    certified_delta_m = radii.pop()
    delta_m = prettify_radius_down(certified_delta_m)

    presentation_centers_by_line = {}
    for line_index, center in centers_by_line.items():
        lo = center - certified_delta_m
        hi = center + certified_delta_m
        for places in range(5, 32):
            rounded_center = round_fraction(center, places)
            if lo <= rounded_center - delta_m and rounded_center + delta_m <= hi:
                presentation_centers_by_line[line_index] = format_fraction_fixed_places(rounded_center, places)
                break
        else:
            raise ValueError(f"failed to find a rounded presentation center for line {line_index}")

    labels_by_line = {item["line"]: item["label"] for item in certificate["a_values"]}

    lines = [
        rf"\providecommand{{\SeedNineteenEpsLower}}{{{scientific_tex(epsilon_lo)}}}",
        rf"\providecommand{{\SeedNineteenEpsUpper}}{{{scientific_tex(epsilon_hi)}}}",
        rf"\providecommand{{\SeedNineteenDeltaM}}{{{scientific_tex(delta_m)}}}",
        r"\refstepcounter{equation}\label{eq:seed19-parameter-box}",
        r"\[",
        r"  \eps \in \left(0,\SeedNineteenEpsUpper\right),",
        r"  \qquad",
        rf"  m_i \in \left[m_i^\ast-\delta_m,m_i^\ast+\delta_m\right],",
        r"  \qquad",
        r"  \delta_m = \SeedNineteenDeltaM.",
        r"  \tag{\theequation}",
        r"\]",
        r"The exact values of slope centers $m_i^\ast$ and $x$-intercepts $a_i$ are:",
        r"\begingroup",
        r"\[",
        r"\renewcommand{\arraystretch}{1.1}",
        r"\begin{array}{ll@{\qquad}ll}",
    ]

    for left_index, right_index in zip(range(1, 10), range(10, 19)):
        left_label_tex = _label_to_tex(labels_by_line[left_index])
        left_center = presentation_centers_by_line[left_index]
        right_label_tex = _label_to_tex(labels_by_line[right_index])
        right_center = presentation_centers_by_line[right_index]
        lines.append(
            rf" m_{{{left_index}}}^\ast = {left_center},"
            rf" & a_{{{left_index}}} = {left_label_tex}"
            rf" & m_{{{right_index}}}^\ast = {right_center},"
            rf" & a_{{{right_index}}} = {right_label_tex}"
            r" \\"
        )

    lines.extend(
        [
            r"\end{array}",
            r"\]",
            r"\endgroup",
            "",
        ]
    )
    return "\n".join(lines)


def render_omatrix(omatrix: list[list[int]]) -> str:
    lines = [
        r"\begin{verbatim}",
        "[",
    ]

    for row_index, row in enumerate(omatrix):
        suffix = "," if row_index + 1 < len(omatrix) else ""
        lines.append(f"  {json.dumps(row)}{suffix}")

    lines.extend(
        [
            "]",
            r"\end{verbatim}",
            "",
        ]
    )
    return "\n".join(lines)


def write_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def prettify_radius_down(radius: Fraction) -> Fraction:
    if radius <= 0:
        raise ValueError(f"radius must be positive, got {radius}")

    exponent = 0
    if radius != 0:
        exponent = len(str(abs(radius.numerator) // radius.denominator)) - 1 if abs(radius) >= 1 else -1
        while Fraction(10) ** exponent > radius:
            exponent -= 1

    while True:
        base = Fraction(10) ** exponent
        for multiplier in (5, 2, 1):
            candidate = multiplier * base
            if candidate <= radius:
                return candidate
        exponent -= 1


def main() -> int:
    certificate = load_json(INTERVAL_CERTIFICATE_PATH)
    omatrix = load_json(OMATRIX_PATH)

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    write_if_changed(NORMALIZED_INCLUDE_PATH, render_normalized_data(certificate))
    write_if_changed(OMATRIX_INCLUDE_PATH, render_omatrix(omatrix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
