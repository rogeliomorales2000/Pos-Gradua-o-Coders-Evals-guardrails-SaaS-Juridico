#!/bin/bash

set -e

echo "========================================"
echo "       LEXAI - PROJECT SETUP"
echo "========================================"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "[1/5] Criando diretórios..."

mkdir -p "$ROOT_DIR/frontend"

mkdir -p "$ROOT_DIR/backend/api"
mkdir -p "$ROOT_DIR/backend/core"
mkdir -p "$ROOT_DIR/backend/models"
mkdir -p "$ROOT_DIR/backend/services"
mkdir -p "$ROOT_DIR/backend/evals"
mkdir -p "$ROOT_DIR/backend/storage/documents"

echo "[OK] Diretórios criados."

echo ""
echo "[2/5] Criando arquivos Python..."

touch "$ROOT_DIR/backend/app.py"
touch "$ROOT_DIR/backend/requirements.txt"
touch "$ROOT_DIR/backend/.env"

touch "$ROOT_DIR/backend/api/__init__.py"
touch "$ROOT_DIR/backend/api/chat.py"
touch "$ROOT_DIR/backend/api/documents.py"
touch "$ROOT_DIR/backend/api/evals.py"

touch "$ROOT_DIR/backend/core/__init__.py"
touch "$ROOT_DIR/backend/core/config.py"
touch "$ROOT_DIR/backend/core/guardrails.py"
touch "$ROOT_DIR/backend/core/prompts.py"

touch "$ROOT_DIR/backend/models/__init__.py"
touch "$ROOT_DIR/backend/models/schemas.py"
touch "$ROOT_DIR/backend/models/llm.py"

touch "$ROOT_DIR/backend/services/__init__.py"
touch "$ROOT_DIR/backend/services/pdf_service.py"
touch "$ROOT_DIR/backend/services/legal_service.py"

touch "$ROOT_DIR/backend/evals/__init__.py"
touch "$ROOT_DIR/backend/evals/dataset.json"
touch "$ROOT_DIR/backend/evals/evaluator.py"

echo "[OK] Arquivos criados."

echo ""
echo "[3/5] Criando .gitkeep..."

touch "$ROOT_DIR/backend/storage/documents/.gitkeep"

echo "[OK] .gitkeep criado."

echo ""
echo "[4/5] Criando ambiente virtual Python..."

cd "$ROOT_DIR/backend"

if command -v python3 &> /dev/null
then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null
then
    PYTHON_CMD="python"
else
    echo "[ERRO] Python não encontrado."
    exit 1
fi

if [ ! -d ".venv" ]; then
    "$PYTHON_CMD" -m venv .venv
    echo "[OK] Ambiente virtual criado."
else
    echo "[INFO] Ambiente virtual já existe."
fi

echo ""
echo "[5/5] Setup concluído."

echo ""
echo "========================================"
echo "             PRÓXIMOS PASSOS"
echo "========================================"

echo ""
echo "Linux/macOS:"
echo ""
echo "cd backend"
echo "source .venv/bin/activate"
echo "pip install -r requirements.txt"
echo "uvicorn app:app --reload --port 8000"

echo ""
echo "Swagger:"
echo "http://localhost:8000/docs"

echo ""
echo "========================================"
echo "          LEXAI PRONTO PARA USO"
echo "========================================"