#!/bin/bash
# ============================================================================
# Script to run EAOS Spark inference job in Docker
# ============================================================================

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}EAOS Spark Job Runner (Docker)${NC}"
echo -e "${BLUE}======================================${NC}"

# Check if docker-compose is running
if ! docker ps | grep -q "tv-analytics-pyspark"; then
    echo -e "${RED}Error: PySpark container not running!${NC}"
    echo -e "Start with: ${GREEN}cd .. && docker-compose up -d pyspark${NC}"
    exit 1
fi

# Default parameters
MODEL_DIR="${MODEL_DIR:-./models/checkpoints}"
INPUT_PATH="${INPUT_PATH:-./data/sample_comments.json}"
OUTPUT_PATH="${OUTPUT_PATH:-./results/predictions.json}"
MODE="${MODE:-console}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --model-dir)
            MODEL_DIR="$2"
            shift 2
            ;;
        --input)
            INPUT_PATH="$2"
            shift 2
            ;;
        --output)
            OUTPUT_PATH="$2"
            shift 2
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --model-dir PATH    Path to model directory (default: ./models/checkpoints)"
            echo "  --input PATH        Input data path (default: ./data/sample_comments.json)"
            echo "  --output PATH       Output path (default: ./results/predictions.json)"
            echo "  --mode MODE         Output mode: console|file|memory (default: console)"
            echo "  --help              Show this help message"
            echo ""
            echo "Examples:"
            echo "  # Run with console output (sample data)"
            echo "  ./run_spark_job.sh"
            echo ""
            echo "  # Run with file input/output"
            echo "  ./run_spark_job.sh --input ./data/comments.json --output ./results/pred.json --mode file"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Display job configuration
echo ""
echo -e "${GREEN}Job Configuration:${NC}"
echo "  Model Dir:  $MODEL_DIR"
echo "  Input:      $INPUT_PATH"
echo "  Output:     $OUTPUT_PATH"
echo "  Mode:       $MODE"
echo ""

# Build command
CMD="python -m ml.spark_inference --model-dir $MODEL_DIR --mode $MODE"

if [ "$MODE" == "file" ]; then
    CMD="$CMD --input $INPUT_PATH --output $OUTPUT_PATH"
elif [ ! -z "$INPUT_PATH" ] && [ "$INPUT_PATH" != "./data/sample_comments.json" ]; then
    CMD="$CMD --input $INPUT_PATH"
fi

# Run job in PySpark container (local mode)
echo -e "${BLUE}Running PySpark job (local mode)...${NC}"
echo -e "${GREEN}Command: $CMD${NC}"
echo ""

# Execute in PySpark container
docker exec -it tv-analytics-pyspark bash -c "$CMD"

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}✅ Job completed successfully!${NC}"
    echo -e "${GREEN}======================================${NC}"
else
    echo ""
    echo -e "${RED}======================================${NC}"
    echo -e "${RED}❌ Job failed!${NC}"
    echo -e "${RED}======================================${NC}"
    exit 1
fi
