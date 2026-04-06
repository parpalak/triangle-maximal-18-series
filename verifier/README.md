# verifier

Two-step certification pipeline for the `n=19` base configuration.

For file and JSON field definitions, see [`../data/n19/FORMAT.md`](../data/n19/FORMAT.md).

## Inputs

The pipeline starts from two files:

- `../data/n19/lines.csv` — floating-point line data;
- `../data/n19/omatrix.json` — the given O-matrix.

## Two-step architecture

The certification is split into two scripts, separating two logically different tasks:

- certifying that the input data realizes the intended Bartholdi–Blanc–Loisel normalized arrangement;
- certifying the combinatorial properties of the O-matrix used in the paper.

### Step 1: `certify_interval.py` — normalization and interval certification

Reads the line data and the O-matrix and reconstructs the normalized arrangement:
$Y_0: y=0$, $L_i: y=m_i(x-a_i)$.

Certifies that:

- the input data can be normalized to Bartholdi–Blanc–Loisel form;
- the values $a_i$ are recognized as the expected exact labels $\pm\tan(k\pi/18)$ and $\pm\varepsilon$;
- the reconstructed arrangement realizes the given O-matrix, verified by interval arithmetic over a parameter box.

Run:

```bash
python3 certify_interval.py \
  --lines ../data/n19/lines.csv \
  --omatrix ../data/n19/omatrix.json \
  --interval-certificate ../data/n19/interval_certificate.json
```

### Step 2: `certify_combinatorial.py` — structural verification

Reads the O-matrix and checks the combinatorial properties used in the paper:

- $Y_0$ touches exactly $17$ triangles;
- the arrangement has exactly $107$ bounded triangular faces.

Run:

```bash
python3 certify_combinatorial.py \
  --omatrix ../data/n19/omatrix.json \
  --certificate ../data/n19/combinatorial_certificate.json
```

## Outputs

The minimal certification package is:

- `lines.csv`
- `omatrix.json`
- `interval_certificate.json`
- `combinatorial_certificate.json`

Everything else in the repository is supporting documentation, implementation, or provenance.

## Tests

Regression tests live in `tests/`.

```bash
python3 -m unittest discover -s tests
```
