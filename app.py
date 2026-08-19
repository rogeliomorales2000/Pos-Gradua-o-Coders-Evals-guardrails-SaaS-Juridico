from fastapi import FastAPI

from fastapi.middleware.cors import (
    CORSMiddleware
)

from api.chat import (
    router as chat_router
)

from api.documents import (
    router as documents_router
)

from api.evals import (
    router as evals_router
)

from core.config import settings


app = FastAPI(

    title="LexAI",

    description=(
        "Assistente de IA para análise "
        "preliminar de contratos empresariais "
        "com Guardrails e Evals."
    ),

    version="1.0.0"

)


# ==========================================
# CORS
# ==========================================

origins = [

    origin.strip()

    for origin

    in settings.cors_origins.split(",")

]


app.add_middleware(

    CORSMiddleware,

    allow_origins=origins,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]

)


# ==========================================
# ROUTERS
# ==========================================

app.include_router(
    chat_router
)

app.include_router(
    documents_router
)

app.include_router(
    evals_router
)


# ==========================================
# ROOT
# ==========================================

@app.get("/")
async def root():

    return {

        "application":
            "LexAI",

        "status":
            "online",

        "version":
            "1.0.0",

        "purpose":
            "Análise preliminar de contratos empresariais",

        "autonomy":
            "human_review_required",

        "endpoints": {

            "chat":
                "/api/chat",

            "pdf":
                "/api/analyze-pdf",

            "evals":
                "/api/evals",

            "documentation":
                "/docs"

        }

    }


# ==========================================
# HEALTH
# ==========================================

@app.get("/health")
async def health():

    return {

        "status":
            "healthy",

        "model":
            settings.model_name,

        "provider":
            settings.model_provider

    }