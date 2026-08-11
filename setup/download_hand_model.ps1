# Download the official MediaPipe Hand Landmarker model used by Level 2.
$projectRoot = Split-Path -Parent $PSScriptRoot
$modelDirectory = Join-Path $projectRoot "assets\models"
$modelPath = Join-Path $modelDirectory "hand_landmarker.task"
$modelUrl = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"

New-Item -ItemType Directory -Force -Path $modelDirectory | Out-Null

if (Test-Path -LiteralPath $modelPath) {
    Write-Host "Hand Landmarker model already exists: $modelPath"
    exit 0
}

Write-Host "Downloading the official MediaPipe Hand Landmarker model..."
Invoke-WebRequest -Uri $modelUrl -OutFile $modelPath
Write-Host "Model ready: $modelPath"
