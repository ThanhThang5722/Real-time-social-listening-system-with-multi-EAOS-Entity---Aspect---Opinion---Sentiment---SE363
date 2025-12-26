# ============================================================================
# PowerShell Script to run EAOS Spark inference job in Docker (Windows)
# ============================================================================

param(
    [string]$ModelDir = "./models/checkpoints",
    [string]$Input = "./data/sample_comments.json",
    [string]$Output = "./results/predictions.json",
    [string]$Mode = "console",
    [switch]$Help
)

function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

if ($Help) {
    Write-ColorOutput "Usage: .\run_spark_job.ps1 [OPTIONS]" "Cyan"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -ModelDir PATH    Path to model directory (default: ./models/checkpoints)"
    Write-Host "  -Input PATH       Input data path (default: ./data/sample_comments.json)"
    Write-Host "  -Output PATH      Output path (default: ./results/predictions.json)"
    Write-Host "  -Mode MODE        Output mode: console|file|memory (default: console)"
    Write-Host "  -Help             Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  # Run with console output (sample data)"
    Write-Host "  .\run_spark_job.ps1"
    Write-Host ""
    Write-Host "  # Run with file input/output"
    Write-Host "  .\run_spark_job.ps1 -Input ./data/comments.json -Output ./results/pred.json -Mode file"
    exit 0
}

Write-ColorOutput "======================================" "Blue"
Write-ColorOutput "EAOS Spark Job Runner (Docker)" "Blue"
Write-ColorOutput "======================================" "Blue"

# Check if PySpark container is running
$running = docker ps | Select-String "tv-analytics-pyspark"
if (-not $running) {
    Write-ColorOutput "Error: PySpark container not running!" "Red"
    Write-ColorOutput "Start with: cd .. ; docker-compose up -d pyspark" "Yellow"
    exit 1
}

# Display job configuration
Write-Host ""
Write-ColorOutput "Job Configuration:" "Green"
Write-Host "  Model Dir:  $ModelDir"
Write-Host "  Input:      $Input"
Write-Host "  Output:     $Output"
Write-Host "  Mode:       $Mode"
Write-Host ""

# Build command
$cmd = "python -m ml.spark_inference --model-dir $ModelDir --mode $Mode"

if ($Mode -eq "file") {
    $cmd += " --input $Input --output $Output"
} elseif ($Input -ne "./data/sample_comments.json") {
    $cmd += " --input $Input"
}

# Run job in PySpark container (local mode)
Write-ColorOutput "Running PySpark job (local mode)..." "Blue"
Write-ColorOutput "Command: $cmd" "Green"
Write-Host ""

# Execute in PySpark container
docker exec -it tv-analytics-pyspark bash -c "$cmd"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-ColorOutput "======================================" "Green"
    Write-ColorOutput "✅ Job completed successfully!" "Green"
    Write-ColorOutput "======================================" "Green"
} else {
    Write-Host ""
    Write-ColorOutput "======================================" "Red"
    Write-ColorOutput "❌ Job failed!" "Red"
    Write-ColorOutput "======================================" "Red"
    exit 1
}
