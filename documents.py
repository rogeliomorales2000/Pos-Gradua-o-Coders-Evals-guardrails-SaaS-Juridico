from pathlib import Path

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException
)

from services.pdf_service import (
    extract_pdf,
    clean_pdf_text,
    create_document_id
)

from services.legal_service import (
    LegalService
)

from core.config import settings


router = APIRouter(
    prefix="/api",
    tags=["Documents"]
)


legal_service = LegalService()


DOCUMENT_DIR = Path(
    "storage/documents"
)

DOCUMENT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


MAX_FILE_SIZE = (
    settings.max_file_size_mb
    * 1024
    * 1024
)


@router.post(
    "/analyze-pdf"
)
async def analyze_pdf(
    file: UploadFile = File(...)
):

    # ==========================================
    # VALIDAÇÃO DO ARQUIVO
    # ==========================================

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="Arquivo não informado."
        )

    filename = Path(
        file.filename
    ).name

    if not filename.lower().endswith(
        ".pdf"
    ):

        raise HTTPException(
            status_code=400,
            detail="Somente arquivos PDF são permitidos."
        )

    # ==========================================
    # LEITURA
    # ==========================================

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:

        raise HTTPException(
            status_code=413,
            detail=(
                f"Arquivo maior que "
                f"{settings.max_file_size_mb} MB."
            )
        )

    # ==========================================
    # EXTRAÇÃO
    # ==========================================

    try:

        extracted = extract_pdf(
            content
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=(
                "Não foi possível "
                "processar o PDF."
            )
        ) from exc

    text = clean_pdf_text(
        extracted["text"]
    )

    if not text:

        return {

            "success": False,

            "message": (
                "O PDF não possui texto "
                "extraível. Será necessário "
                "adicionar OCR para documentos "
                "digitalizados."
            )

        }

    # ==========================================
    # ID
    # ==========================================

    document_id = create_document_id()

    document_path = (
        DOCUMENT_DIR
        / f"{document_id}.pdf"
    )

    document_path.write_bytes(
        content
    )

    # ==========================================
    # CONTEXTO
    # ==========================================

    context = text[
        :settings.max_text_length
    ]

    # ==========================================
    # ANÁLISE
    # ==========================================

    result = legal_service.chat(

        message=(
            "Analise preliminarmente "
            "este contrato empresarial. "
            "Identifique os principais "
            "riscos jurídicos e pontos "
            "de atenção."
        ),

        context=context,

        document_id=document_id

    )

    # ==========================================
    # RESPOSTA
    # ==========================================

    return {

        "success": True,

        "document_id":
            document_id,

        "filename":
            filename,

        "pages":
            extracted["page_count"],

        "summary":
            result["answer"],

        "risk_level":
            result["risk_level"],

        "risk_score":
            result["risk_score"],

        "confidence":
            result["confidence"],

        "requires_human_review":
            result[
                "requires_human_review"
            ],

        "findings":
            result["findings"],

        "guardrail_flags":
            result[
                "guardrail_flags"
            ]

    }