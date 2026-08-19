from typing import Dict, Any

from core.prompts import SYSTEM_PROMPT


class LegalModel:

    def generate(
        self,
        user_message: str,
        context: str = ""
    ) -> Dict[str, Any]:

        raise NotImplementedError


class MockLegalModel(LegalModel):

    def generate(
        self,
        user_message: str,
        context: str = ""
    ):

        message = user_message.lower()

        context_lower = context.lower()

        findings = []

        # -----------------------------------------
        # RESCISÃO
        # -----------------------------------------

        if (
            "rescis" in message
            or "rescis" in context_lower
        ):

            findings.append({

                "category": "Rescisão",

                "severity": "média",

                "description": (
                    "Foi identificada referência "
                    "a mecanismos de rescisão. "
                    "É necessária avaliação das "
                    "condições, prazos e efeitos "
                    "previstos no documento."
                ),

                "recommendation": (
                    "Revisar as condições de "
                    "rescisão e respectivos prazos."
                )

            })

        # -----------------------------------------
        # MULTA
        # -----------------------------------------

        if (
            "multa" in message
            or "penalidade" in message
            or "multa" in context_lower
        ):

            findings.append({

                "category": "Multa",

                "severity": "alta",

                "description": (
                    "Foi identificada previsão "
                    "relacionada a multa ou penalidade."
                ),

                "recommendation": (
                    "Avaliar proporcionalidade, "
                    "hipóteses de aplicação, "
                    "limites e condições."
                )

            })

        # -----------------------------------------
        # LGPD
        # -----------------------------------------

        if (
            "lgpd" in message
            or "dados pessoais" in context_lower
            or "proteção de dados" in context_lower
        ):

            findings.append({

                "category": "Proteção de dados",

                "severity": "média",

                "description": (
                    "Há elementos relacionados "
                    "ao tratamento de dados pessoais."
                ),

                "recommendation": (
                    "Verificar responsabilidades, "
                    "obrigações contratuais e "
                    "tratamento de dados."
                )

            })

        # -----------------------------------------
        # RESPONSABILIDADE
        # -----------------------------------------

        if (
            "responsabilidade" in message
            or "responsabilidade" in context_lower
        ):

            findings.append({

                "category": "Responsabilidade",

                "severity": "alta",

                "description": (
                    "Foi identificada disposição "
                    "relacionada à responsabilidade "
                    "das partes."
                ),

                "recommendation": (
                    "Avaliar limites, hipóteses "
                    "de responsabilização e "
                    "eventuais exclusões."
                )

            })

        # -----------------------------------------
        # CONFIDENCIALIDADE
        # -----------------------------------------

        if (
            "confidencialidade" in message
            or "confidencialidade" in context_lower
        ):

            findings.append({

                "category": "Confidencialidade",

                "severity": "média",

                "description": (
                    "Foi identificada disposição "
                    "relacionada à confidencialidade."
                ),

                "recommendation": (
                    "Verificar abrangência, "
                    "prazo e exceções."
                )

            })

        # -----------------------------------------
        # RESULTADO
        # -----------------------------------------

        if not findings:

            answer = (
                "A análise preliminar não identificou "
                "automaticamente um ponto específico "
                "suficiente para uma conclusão jurídica. "
                "Recomenda-se revisar o documento "
                "integralmente e validar os pontos "
                "relevantes com um profissional jurídico."
            )

            risk_level = "baixo"

            risk_score = 20

            confidence = 0.72

        else:

            answer = (
                f"Foram identificados {len(findings)} "
                "ponto(s) de atenção no contexto analisado. "
                "A classificação é preliminar e não "
                "representa parecer jurídico definitivo."
            )

            if any(
                item["severity"] == "alta"
                for item in findings
            ):

                risk_level = "alto"

                risk_score = 75

            else:

                risk_level = "médio"

                risk_score = 50

            confidence = 0.72

        return {

            "answer": answer,

            "risk_level": risk_level,

            "risk_score": risk_score,

            "confidence": confidence,

            "findings": findings

        }


def get_model():

    return MockLegalModel()