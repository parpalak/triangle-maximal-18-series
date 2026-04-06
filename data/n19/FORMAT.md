# n=19 data format

Format specification for the input data and certificates.

## 1. `lines.csv`

Purpose: floating-point coefficients of the `19` lines; primary geometric input to the verifier.

Required columns:

```text
m,b
```

- `m` — slope in the affine form $y = mx + b$;
- `b` — intercept.

Requirements:

- exactly `19` data rows;
- row order defines line numbering $0, 1, \ldots, 18$;
- the first row is $Y_0$ with `m=0`, `b=0`.

Example:

```csv
m,b
0,0
0.00204210558109587956701,-0.0115813562558089199685
0.002017527449068954479,0.00240439558558535845824
```

## 2. `omatrix.json`

Purpose: the O-matrix encoding of the combinatorial type; input for both verification steps.

Format:

```json
[
  [18, 6, 16, 2, 14, 4, 17, 10, 12, 8, 15, 7, 13, 5, 11, 3, 9, 1]
]
```

Requirements:

- array of `19` rows, each of length `18`;
- row $i$ records the order of intersections along line $i$;
- row $i$ contains each index in $\{0, \ldots, 18\} \setminus \{i\}$ exactly once.

## 3. `interval_certificate.json`

Purpose: output of the first verification step; certifies that the input data can be transformed into the exact normalized form of Bartholdi–Blanc–Loisel iterative step that realizes the given O-matrix.

Minimal format:

```json
{
  "n": 19,
  "input_checksum": "...",
  "omatrix_checksum": "...",
  "normalization": {
    "y0_line": 0,
    "order_for_rows_1_to_18": "descending_y",
    "special_lines": [17, 18]
  },
  "a_values": [
    {"line": 1, "label": "-tan(8pi/18)", "recovered_from_input": "-5.671281819617709"},
    {"line": 18, "label": "+epsilon", "recovered_from_input": "0.000001"}
  ],
  "m_values": [
    {"line": 1, "recovered_from_input": "0.00204210558109587956701"}
  ],
  "epsilon": {
    "recovered_from_input": "0.000001",
    "interval": ["1/2000000", "1/500000"]
  },
  "m_intervals": [
    {"line": 1, "interval": ["0.00204210", "0.00204211"]}
  ],
  "checked_rows": [1, 2, 3],
  "row_order_inequalities_count": 306,
  "row_order_min_margin": "1/1000000000",
  "parallel_separation_min_margin": "1/1000000000",
  "omatrix_realized_by_bbl": true,
  "verdict": true,
  "diagnostics": {
    "epsilon_zero_limit": {
      "ok": true,
      "zero_inequalities": [
        {"row": 8, "position": 10, "left": 12, "right": 0}
      ],
      "zero_inequalities_count": 2,
      "negative_inequalities": [],
      "negative_inequalities_count": 0,
      "required_zero_inequalities_count": 2,
      "special_lines": [17, 18]
    }
  }
}
```

### Fields

- `n`: number of lines;
- `input_checksum`: SHA-256 of `lines.csv`;
- `omatrix_checksum`: SHA-256 of `omatrix.json`;
- `normalization`: description of the normalized form;
  - `y0_line`: which line plays the role of $Y_0$;
  - `order_for_rows_1_to_18`: convention for row ordering (`descending_y`);
  - `special_lines`: the two lines corresponding to $\pm\varepsilon$;
- `a_values`: correspondence between lines and exact $a_i$ labels (e.g. $\pm\tan(k\pi/18)$, $\pm\varepsilon$);
- `m_values`: slopes $m_i$ computed from the input after normalization;
- `epsilon`: the special parameter $\varepsilon$ with a certified interval;
- `m_intervals`: certified interval box for the slopes $m_i$;
- `checked_rows`: O-matrix rows for which interval inequalities were checked;
- `row_order_inequalities_count`: total number of order inequalities checked (for $n=19$: $18 \times 17 = 306$);
- `row_order_min_margin`: smallest margin among all order inequalities;
- `parallel_separation_min_margin`: smallest margin in the conditions $m_i \ne m_j$;
- `omatrix_realized_by_bbl`: whether the normalized arrangement realizes the given O-matrix;
- `verdict`: final verdict of the first step;
- `diagnostics.epsilon_zero_limit`: check of the limiting regime $\varepsilon = 0$.

### Interval arithmetic

The intersection height of lines $i$ and $j$ along line $i$ is
$y_{i,j} = m_i m_j (a_i - a_j) / (m_i - m_j)$.

If $O[i] = (j_1, \ldots, j_{18})$, then for each row $i > 0$ the verifier checks
$y_{i,j_1} > y_{i,j_2} > \cdots > y_{i,j_{18}}$,
i.e. $17$ adjacent inequalities per row.

Row $Y_0$ need not be checked by interval arithmetic if its order is already fixed by the exact structure of $a_i$ and $\varepsilon$.

### Limiting check at $\varepsilon = 0$

- On the certified interval, all order inequalities remain strict.
- At $\varepsilon = 0$, exactly two adjacent inequalities degenerate to equalities and none become negative.

### Meaning of `verdict`

The normalized arrangement has been reconstructed from the input data; the exact labels $a_i$ and the special lines have been recognized; all order inequalities hold on the certified interval box; the given O-matrix is realized.

## 4. `combinatorial_certificate.json`

Purpose: output of the second verification step; certifies the combinatorial properties of the O-matrix used in the paper.

Minimal format:

```json
{
  "n": 19,
  "omatrix_checksum": "...",
  "touching_segments": 17,
  "touching_condition_on_Y0": true,
  "bounded_triangles": 107,
  "verdict": true
}
```

### Fields

- `omatrix_checksum`: SHA-256 of the O-matrix;
- `touching_segments`: number of segments on $Y_0$ that are sides of triangles;
- `touching_condition_on_Y0`: whether $Y_0$ touches exactly $17$ triangles;
- `bounded_triangles`: number of bounded triangular faces;
- `verdict`: final verdict of the second step.

### Meaning of `verdict`

The touching condition holds on $Y_0$, and the arrangement has the expected number of bounded triangles.

Note: the actual certificate file may contain additional diagnostic fields beyond this minimal specification.
