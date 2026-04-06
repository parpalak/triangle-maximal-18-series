#!/usr/bin/env bash
#
# Pack the preprint for arXiv submission.
#
# Usage: cd preprint && bash pack_arxiv.sh
#
# Produces: arxiv.tar.gz ready for upload.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Regenerate includes (same as latexmkrc does before pdflatex)
echo "==> Regenerating generated includes..."
python3 scripts/generate_seed19_tex_includes.py

# 2. Compile to produce .bbl
echo "==> Compiling to produce .bbl..."
TMPBUILD="$(mktemp -d)"
trap 'rm -rf "$TMPBUILD"' EXIT

cp main.tex arxiv_preamble.sty "$TMPBUILD/"
cp -r sections figures generated "$TMPBUILD/"
cp refs.bib "$TMPBUILD/"
(cd "$TMPBUILD" && pdflatex -interaction=nonstopmode main.tex > /dev/null)
(cd "$TMPBUILD" && bibtex main > /dev/null 2>&1)
(cd "$TMPBUILD" && pdflatex -interaction=nonstopmode main.tex > /dev/null)
(cd "$TMPBUILD" && pdflatex -interaction=nonstopmode main.tex > /dev/null)

if [ ! -f "$TMPBUILD/main.bbl" ]; then
    echo "ERROR: main.bbl was not produced" >&2
    exit 1
fi

# 3. Assemble tarball contents
PACK="$(mktemp -d)"
trap 'rm -rf "$TMPBUILD" "$PACK"' EXIT

# Copy source files preserving directory structure
cp main.tex arxiv_preamble.sty "$PACK/"
cp "$TMPBUILD/main.bbl" "$PACK/"

mkdir -p "$PACK/sections" "$PACK/figures" "$PACK/generated"
cp sections/*.tex "$PACK/sections/"
cp figures/*.tex "$PACK/figures/"
cp generated/*.tex "$PACK/generated/"

# 4. Strip %-comments from all .tex files (keep %% and blank-line %)
echo "==> Stripping comments..."
find "$PACK" -name '*.tex' -print0 | while IFS= read -r -d '' f; do
    # Remove lines that are pure comments (optional leading whitespace + %)
    # Remove trailing comments on code lines (but keep \% escapes)
    sed -i \
        -e '/^[[:space:]]*%/d' \
        -e 's/\([^\\]\)%.*/\1/' \
        "$f"
done

# 5. Create tarball
echo "==> Packing arxiv.tar.gz..."
tar -czf "$SCRIPT_DIR/arxiv.tar.gz" -C "$PACK" .

# 6. Report
echo ""
echo "Done! Contents:"
tar -tzf "$SCRIPT_DIR/arxiv.tar.gz" | sort
echo ""
echo "Archive: $SCRIPT_DIR/arxiv.tar.gz"
