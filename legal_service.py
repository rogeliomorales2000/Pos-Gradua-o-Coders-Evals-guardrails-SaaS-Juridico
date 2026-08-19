from models.llm import get_model

from core.guardrails import (
    run_input_guardrails,
    validate_model_output
)

from core.config import settings


class LegalService:

    def __init__(self):

        self.model = get_model()

    def chat(
        self,
        message: str,
        context: str = "",
        document_id=None
    ):

        # ==========================================
        # INPUT GUARDRAILS
        # ==========================================

        guardrail = run_input_guardrails(
            message
        )

        if not guardrail.allowed:

            return {

                "success": True,

                "answer": (
                    "Não posso processar essa "
                    "solicitação porque ela está "
                    "fora do escopo do assistente "
                    "jurídico empresarial ou "
                    "apresenta uma solicitação "
                    "incompatível com o nível de "
                    "autonomia permitido."
                ),

                "risk_level": "alto",

                "risk_score": 90,

                "confidence": 0.99,

                "requires_human_review": True,

                "findings": [],

                "unsupported_claims": [],

                "scope_violation": True,

                "guardrail_flags":
                    guardrail.flags,

                "document_id":
                    document_id

            }

        # ==========================================
        # MODELO
        # ==========================================

        model_result = self.model.generate(

            user_message=message,

            context=context

        )

        # ==========================================
        # OUTPUT GUARDRAILS
        # ==========================================

        output_guardrail = (
            validate_model_output(
                model_result["answer"]
            )
        )

        if not output_guardrail.allowed:

            return {

                "success": True,

                "answer": (
                    "A resposta gerada pelo "
                    "modelo não passou pela "
                    "validação de segurança. "
                    "Não é possível fornecer "
                    "uma conclusão confiável "
                    "com os dados disponíveis."
                ),

                "risk_level": "alto",

                "risk_score": 90,

                "confidence": 0.0,

                "requires_human_review": True,

                "findings": [],

                "unsupported_claims":
                    output_guardrail.flags,

                "scope_violation": False,

                "guardrail_flags": (
                    guardrail.flags
                    +
                    output_guardrail.flags
                ),

                "document_id":
                    document_id

            }

        confidence = model_result.get(
            "confidence",
            0.0
        )

        risk_level = model_result.get(
            "risk_level",
            "baixo"
        )

        findings = model_result.get(
            "findings",
            []
        )

        requires_review = (

            confidence
            < settings.confidence_threshold

            or risk_level in [
                "alto",
                "crítico",
                "critico"
            ]

            or len(findings) > 0

        )

        return {

            "success": True,

            "answer":
                model_result["answer"],

            "risk_level":
                risk_level,

            "risk_score":
                model_result.get(
                    "risk_score",
                    0
                ),

            "confidence":
                confidence,

            "requires_human_review":
                requires_review,

            "findings":
                findings,

            "unsupported_claims":
                [],

            "scope_violation":
                False,

            "guardrail_flags":
                guardrail.flags,

            "document_id":
                document_id

        }