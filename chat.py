from fastapi import APIRouter

from models.schemas import (
    ChatRequest,
    LegalResponse
)

from services.legal_service import (
    LegalService
)


router = APIRouter(
    prefix="/api",
    tags=["Chat"]
)


legal_service = LegalService()


@router.post(
    "/chat",
    response_model=LegalResponse
)
async def chat(
    request: ChatRequest
):

    result = legal_service.chat(

        message=request.message,

        context="",

        document_id=
            request.document_id

    )

    return result