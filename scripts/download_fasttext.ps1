# Download FastText language identification model
# PowerShell version for Windows

$RESOURCES_DIR = "nlp\lang_detect\resources"
$MODEL_FILE = "lid.176.bin"
$MODEL_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/$MODEL_FILE"

Write-Host "Downloading FastText language identification model..." -ForegroundColor Green

# Create resources directory if it doesn't exist
if (-not (Test-Path $RESOURCES_DIR)) {
    New-Item -ItemType Directory -Path $RESOURCES_DIR -Force | Out-Null
}

$MODEL_PATH = Join-Path $RESOURCES_DIR $MODEL_FILE

# Download model if not already present
if (Test-Path $MODEL_PATH) {
    Write-Host "Model already exists at $MODEL_PATH" -ForegroundColor Yellow
} else {
    Write-Host "Downloading from $MODEL_URL..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $MODEL_URL -OutFile $MODEL_PATH
    Write-Host "Download complete!" -ForegroundColor Green
}

Write-Host "FastText model ready at $MODEL_PATH" -ForegroundColor Green
