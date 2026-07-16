#!/usr/bin/env bash
set -e

# ═══════════════════════════════════════════════════════════
# Sentinel Swarm — Start Everything
# ═══════════════════════════════════════════════════════════

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

banner() {
    echo ""
    echo -e "${PURPLE}  ╔══════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}  ║${NC}  🛡️  ${BLUE}SENTINEL SWARM${NC} — AROS              ${PURPLE}║${NC}"
    echo -e "${PURPLE}  ║${NC}  Autonomous Risk Operating System       ${PURPLE}║${NC}"
    echo -e "${PURPLE}  ╚══════════════════════════════════════════╝${NC}"
    echo ""
}

log() { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }
wait_for() {
    local url=$1 name=$2 max=$3
    for i in $(seq 1 "$max"); do
        if curl -s "$url" > /dev/null 2>&1; then
            log "$name ready"
            return 0
        fi
        sleep 1
    done
    warn "$name not responding after ${max}s (may still be starting)"
}

cleanup() {
    echo ""
    echo -e "  ${YELLOW}Shutting down...${NC}"
    # Kill API and Dashboard
    [ -f "$LOG_DIR/api.pid" ] && kill "$(cat "$LOG_DIR/api.pid")" 2>/dev/null && rm "$LOG_DIR/api.pid"
    [ -f "$LOG_DIR/dashboard.pid" ] && kill "$(cat "$LOG_DIR/dashboard.pid")" 2>/dev/null && rm "$LOG_DIR/dashboard.pid"
    # Stop Docker
    docker compose -f "$ROOT/docker/docker-compose.yml" down 2>/dev/null
    log "All services stopped."
}

trap cleanup INT TERM

# ═══════════════════════════════════════════════════════════

banner

# 1. Check prerequisites
echo -e "  ${BLUE}[1/5]${NC} Checking prerequisites..."

command -v docker >/dev/null 2>&1 || fail "Docker not installed"
command -v python3.12 >/dev/null 2>&1 || fail "Python 3.12 not found. Run: brew install python@3.12"

# Ensure Docker daemon is running
if ! docker info > /dev/null 2>&1; then
    warn "Docker daemon not running — starting Docker Desktop..."
    open -a Docker 2>/dev/null || true
    echo -n "  Waiting for Docker"
    for i in $(seq 1 60); do
        if docker info > /dev/null 2>&1; then
            echo ""
            log "Docker daemon started"
            break
        fi
        echo -n "."
        sleep 2
        if [ "$i" -eq 60 ]; then
            echo ""
            fail "Docker daemon didn't start after 120s. Open Docker Desktop manually."
        fi
    done
fi
log "Docker + Python 3.12 found"

# 2. Virtual environment
echo -e "  ${BLUE}[2/5]${NC} Setting up Python environment..."

if [ ! -d "$VENV" ]; then
    python3.12 -m venv "$VENV"
    log "Created virtualenv"
fi
source "$VENV/bin/activate"

# Check if packages installed
if ! python -c "import sentinel_swarm" 2>/dev/null; then
    pip install -e "$ROOT[dev]" > "$LOG_DIR/pip.log" 2>&1
    pip install streamlit plotly httpx >> "$LOG_DIR/pip.log" 2>&1
    log "Dependencies installed"
else
    log "Dependencies already installed"
fi

# 3. Docker services
echo -e "  ${BLUE}[3/5]${NC} Starting infrastructure..."

# Kill anything on our ports first
for port in 7474 7687 9092 6379 8000; do
    lsof -ti:$port 2>/dev/null | xargs kill -9 2>/dev/null || true
done

if ! docker compose -f "$ROOT/docker/docker-compose.yml" up -d > "$LOG_DIR/docker.log" 2>&1; then
    warn "Some containers may have failed — check logs/docker.log"
    cat "$LOG_DIR/docker.log" | tail -5
else
    log "Docker containers starting"
fi

wait_for "http://localhost:7474" "Neo4j" 30
wait_for "http://localhost:6379" "Redis" 10 2>/dev/null || log "Redis started (no HTTP)"
wait_for "http://localhost:8000/api/v1/heartbeat" "ChromaDB" 15

# 4. API
echo -e "  ${BLUE}[4/5]${NC} Starting API server..."

# Kill previous API if running
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

cd "$ROOT"
nohup python -m uvicorn sentinel_swarm.api.app:app \
    --host 0.0.0.0 --port 3000 \
    > "$LOG_DIR/api.log" 2>&1 &
echo $! > "$LOG_DIR/api.pid"

wait_for "http://localhost:3000/health" "API" 15

# 5. Dashboard
echo -e "  ${BLUE}[5/5]${NC} Starting dashboard..."

lsof -ti:8501 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

nohup python -m streamlit run "$ROOT/dashboard.py" \
    --server.port 8501 \
    --server.headless true \
    --server.address 0.0.0.0 \
    --theme.base dark \
    > "$LOG_DIR/dashboard.log" 2>&1 &
echo $! > "$LOG_DIR/dashboard.pid"

wait_for "http://localhost:8501" "Dashboard" 10

# ═══════════════════════════════════════════════════════════
# Done
# ═══════════════════════════════════════════════════════════

echo ""
echo -e "  ${GREEN}══════════════════════════════════════════${NC}"
echo -e "  ${GREEN}  All systems operational${NC}"
echo -e "  ${GREEN}══════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BLUE}Dashboard${NC}   http://localhost:8501"
echo -e "  ${BLUE}API${NC}         http://localhost:3000"
echo -e "  ${BLUE}Swagger${NC}     http://localhost:3000/docs"
echo -e "  ${BLUE}Neo4j${NC}       http://localhost:7474"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop everything${NC}"
echo ""

# Keep alive — wait for Ctrl+C
wait
