#!/bin/bash

# Exit on error
set -e

BUMP_TYPE=${1:-patch}

echo "🚀 Starting release process with $BUMP_TYPE bump..."

PACKAGE_DIR="fastapi_startkit"

if [ -d "$PACKAGE_DIR" ]; then
    echo "📦 Releasing package: $PACKAGE_DIR"

    # Navigate to package directory
    cd "$PACKAGE_DIR"

    # Bump version
    echo "   Bumping version..."
    uv version --bump "$BUMP_TYPE"
    VERSION=$(uv version --short)

    # Build
    echo "   Building..."
    rm -rf dist/
    uv build

    # Publish via twine
    echo "   Publishing..."
    uv run twine upload dist/* --verbose

    echo "📌 Committing version bump..."
    git add pyproject.toml
    git commit -m "chore: release v$VERSION"

    echo "🏷️ Creating git tag..."
    git tag "v$VERSION"

    echo "⬆️ Pushing commits + tags..."
    git push origin main
    git push origin "v$VERSION"

    echo "🚀 Creating GitHub release..."

    PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

    if [ -n "$PREV_TAG" ]; then
        git log "$PREV_TAG..HEAD" --pretty=format:"- %s" > CHANGELOG.tmp
    else
        git log --pretty=format:"- %s" > CHANGELOG.tmp
    fi

    gh release create "v$VERSION" \
        --title "v$VERSION" \
        --notes-file CHANGELOG.tmp

    rm CHANGELOG.tmp

    cd - > /dev/null
    echo "✅ Release complete: v$VERSION"
else
    echo "⚠️  Package directory $PACKAGE_DIR not found."
    exit 1
fi
