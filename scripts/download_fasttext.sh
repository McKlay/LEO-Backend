#!/usr/bin/env bash
# Download FastText language identification model

set -e

RESOURCES_DIR="nlp/lang_detect/resources"
MODEL_FILE="lid.176.bin"
MODEL_URL="https://dl.fbaipublicfiles.com/fasttext/supervised-models/${MODEL_FILE}"

echo "Downloading FastText language identification model..."

# Create resources directory if it doesn't exist
mkdir -p "${RESOURCES_DIR}"

# Download model if not already present
if [ -f "${RESOURCES_DIR}/${MODEL_FILE}" ]; then
    echo "Model already exists at ${RESOURCES_DIR}/${MODEL_FILE}"
else
    echo "Downloading from ${MODEL_URL}..."
    curl -L -o "${RESOURCES_DIR}/${MODEL_FILE}" "${MODEL_URL}"
    echo "Download complete!"
fi

echo "FastText model ready at ${RESOURCES_DIR}/${MODEL_FILE}"
