#!/usr/bin/env bash
set -euo pipefail

# Publish EarlyCore CLI templates to GitHub Releases and GCS.
#
# Usage:
#   ./scripts/publish-templates.sh 0.1.0
#
# Prerequisites:
#   - gh CLI authenticated (for GitHub Releases)
#
# What it does:
#   1. Creates a tar.gz archive of the template
#   2. Computes SHA-256 checksum
#   3. Updates manifest.json with the new version + checksum
#   4. Uploads to GitHub Releases on the public earlycore-templates repo
#   5. Pushes updated manifest.json to the templates repo
#   6. Prints verification commands

VERSION="${1:?Usage: $0 <version> (e.g. 0.1.0)}"
TEMPLATE="rag-agent"
REPO="EarlyCore-AI/earlycore-templates"
TAG="v${VERSION}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$SCRIPT_DIR"
DIST_DIR="${REPO_DIR}/dist"

echo "=== Publishing ${TEMPLATE} v${VERSION} ==="

# 1. Create archive
mkdir -p "$DIST_DIR"
ARCHIVE="${DIST_DIR}/${TEMPLATE}-v${VERSION}.tar.gz"
echo "Creating archive..."
tar -czf "$ARCHIVE" -C "$REPO_DIR" "$TEMPLATE"
echo "  Archive: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# 2. Compute checksum
CHECKSUM=$(shasum -a 256 "$ARCHIVE" | cut -d' ' -f1)
echo "  SHA-256: $CHECKSUM"

# 3. Update manifest.json
MANIFEST="${REPO_DIR}/manifest.json"
GITHUB_URL="https://github.com/${REPO}/releases/download/v${VERSION}/${TEMPLATE}-v${VERSION}.tar.gz"

python3 -c "
import json, sys
with open('${MANIFEST}') as f:
    m = json.load(f)
t = m.setdefault('templates', {}).setdefault('${TEMPLATE}', {})
t['latest'] = '${VERSION}'
v = t.setdefault('versions', {})
v['${VERSION}'] = {
    'sha256': '${CHECKSUM}',
    'sources': ['${GITHUB_URL}']
}
with open('${MANIFEST}', 'w') as f:
    json.dump(m, f, indent=2)
    f.write('\n')
print('  Manifest updated')
"

# 4. Upload to GitHub Releases
echo ""
echo "=== GitHub Release ==="
if command -v gh &>/dev/null; then
    # Create release if it doesn't exist
    if ! gh release view "$TAG" --repo "$REPO" &>/dev/null; then
        gh release create "$TAG" \
            --repo "$REPO" \
            --title "CLI Templates v${VERSION}" \
            --notes "EarlyCore CLI templates release v${VERSION}.

**SHA-256 checksums:**
\`\`\`
${CHECKSUM}  ${TEMPLATE}-v${VERSION}.tar.gz
\`\`\`

**Verify after download:**
\`\`\`bash
echo '${CHECKSUM}  ${TEMPLATE}-v${VERSION}.tar.gz' | shasum -a 256 --check
\`\`\`"
        echo "  Release created: $TAG"
    fi
    gh release upload "$TAG" "$ARCHIVE" --repo "$REPO" --clobber
    echo "  Uploaded to GitHub Releases"
else
    echo "  SKIP: gh CLI not found. Install: https://cli.github.com"
fi

# 5. Commit and push updated manifest
echo ""
echo "=== Commit manifest ==="
cd "$REPO_DIR"
git add manifest.json
git commit -m "Release ${TEMPLATE} v${VERSION} (sha256: ${CHECKSUM:0:16}...)" && \
    git push && \
    echo "  Manifest committed and pushed" || \
    echo "  WARNING: Could not push manifest. Commit and push manually."

# 6. Verification
echo ""
echo "=== Verification ==="
echo "  GitHub: https://github.com/${REPO}/releases/tag/${TAG}"
echo "  SHA-256: ${CHECKSUM}"
echo ""
echo "  Users verify with:"
echo "    earlycore templates  # lists available templates with versions"
echo ""
echo "  Manual verify:"
echo "    curl -sL ${GITHUB_URL} | shasum -a 256"
echo "    Expected: ${CHECKSUM}"
