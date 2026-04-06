# The 18·2^t+1 Triangle-Maximal Series

Public repository for the certified `n=19` base configuration used in the paper.

This repository is the artifact cited by the preprint. It bundles:

- the preprint source;
- the `n=19` input data;
- the certification scripts;
- the generated certificate files.

## Quickstart

Run the two certification steps from [`verifier/`](./verifier):

```bash
cd verifier
python3 certify_interval.py \
  --lines ../data/n19/lines.csv \
  --omatrix ../data/n19/omatrix.json \
  --interval-certificate ../data/n19/interval_certificate.json
python3 certify_combinatorial.py \
  --omatrix ../data/n19/omatrix.json \
  --certificate ../data/n19/combinatorial_certificate.json
```

This writes:

- `data/n19/interval_certificate.json`
- `data/n19/combinatorial_certificate.json`

## Repository structure

- [`data/n19/`](./data/n19/README.md) — input data and generated certificates. See also [`FORMAT.md`](./data/n19/FORMAT.md) for field definitions.
- [`verifier/`](./verifier/README.md) — certification pipeline: scripts, commands, and tests.
- [`preprint/`](./preprint/) — paper source (LaTeX).
- [`docs/`](./docs/) — GitHub Pages: [Line Configuration Viewer](https://parpalak.github.io/triangle-maximal-18-series/viewer/), [Gallery](https://parpalak.github.io/triangle-maximal-18-series/gallery/).
- [`gallery/`](./gallery/) — source for gallery generation.
