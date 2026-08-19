import re
from dataclasses import dataclass
from typing import List


@dataclass
class GuardrailResult:

    allowed: bool

    flags: List[str]

    reason: str = ""


LEGAL_TOPICS = [

    "contrato",
    "contratos",

    "cláusula",
    "clausula",
    "cláusulas",
    "clausulas",

    "contratual",

    "rescisão",
    "rescisao",

    "multa",
    "multas",

    "penalidade",
    "penalidades",

    "indenização",
    "indenizacao",

    "responsabilidade",

    "confidencialidade",

    "lgpd",

    "dados pessoais",

    "proteção de dados",
    "protecao de dados",

    "prazo",
    "prazos",

    "obrigação",
    "obrigacao",

    "jurisdição",
    "jurisdicao",

    "foro",

    "propriedade intelectual",

    "licenciamento",

    "compliance",

    "risco jurídico",
    "risco juridico",

    "contraparte",

    "prestação de serviços",
    "prestacao de servicos",

    "acordo",

    "termo",

    "aditivo",

]


OUT_OF_SCOPE_TOPICS = [

    "como hackear",
    "como invadir",

    "malware",
    "ransomware",

    "explosivo",
    "explosivos",

    "arma de fogo",

    "roubar senha",

    "roubar senhas",

    "phishing",

]


PROMPT_INJECTION_PATTERNS = [

    r"ignore\s+(todas\s+)?as\s+instruções",

    r"ignore\s+(all\s+)?previous\s+instructions",

    r"ignore\s+o\s+sistema",

    r"ignore\s+as\s+regras",

    r"desconsidere\s+as\s+instruções",

    r"desconsidere\s+as\s+regras",

    r"system\s+prompt",

    r"mostre\s+seu\s+prompt",

    r"revele\s+suas\s+instruções",

    r"revele\s+o\s+prompt",

    r"finja\s+que\s+você\s+é",

    r"você\s+agora\s+é",

]


HIGH_AUTONOMY_PATTERNS = [

    r"assine\s+o\s+contrato",

    r"assinar\s+o\s+contrato",

    r"aprovar\s+o\s+contrato",

    r"aprove\s+o\s+contrato",

    r"posso\s+assinar",

    r"podemos\s+assinar",

    r"dê\s+parecer\s+definitivo",

    r"dar\s+parecer\s+definitivo",

    r"parecer\s+jurídico\s+definitivo",

    r"parecer\s+juridico\s+definitivo",

    r"garanta\s+que\s+é\s+legal",

    r"garanta\s+que\s+este\s+contrato\s+é\s+legal",

]


DANGEROUS_OUTPUT_PATTERNS = [

    "garanto que é legal",

    "garanto que e legal",

    "garanto que é ilegal",

    "garanto que e ilegal",

    "pode assinar sem revisão",

    "assine sem revisão",

    "não precisa de advogado",

    "nao precisa de advogado",

    "contrato aprovado",

    "isso é definitivamente legal",

    "isso e definitivamente legal",

    "isso é definitivamente ilegal",

    "isso e definitivamente ilegal",

]


def detect_prompt_injection(text: str) -> bool:

    normalized = text.lower()

    for pattern in PROMPT_INJECTION_PATTERNS:

        if re.search(
            pattern,
            normalized
        ):
            return True

    return False


def detect_autonomy_request(text: str) -> bool:

    normalized = text.lower()

    for pattern in HIGH_AUTONOMY_PATTERNS:

        if re.search(
            pattern,
            normalized
        ):
            return True

    return False


def detect_out_of_scope(text: str) -> bool:

    normalized = text.lower()

    for topic in OUT_OF_SCOPE_TOPICS:

        if topic in normalized:
            return True

    return False


def detect_legal_context(text: str) -> bool:

    normalized = text.lower()

    for topic in LEGAL_TOPICS:

        if topic in normalized:
            return True

    return False


def run_input_guardrails(
    text: str
) -> GuardrailResult:

    flags = []

    if not text or not text.strip():

        return GuardrailResult(
            allowed=False,
            flags=["empty_input"],
            reason="A mensagem está vazia."
        )

    if detect_prompt_injection(text):

        flags.append(
            "prompt_injection_detected"
        )

    if detect_autonomy_request(text):

        flags.append(
            "high_autonomy_request"
        )

    if detect_out_of_scope(text):

        flags.append(
            "out_of_scope"
        )

    if not detect_legal_context(text):

        flags.append(
            "legal_context_unclear"
        )

    critical_flags = {

        "prompt_injection_detected",

        "out_of_scope"

    }

    if critical_flags.intersection(
        flags
    ):

        return GuardrailResult(

            allowed=False,

            flags=flags,

            reason=(
                "A solicitação está fora do "
                "escopo ou contém uma tentativa "
                "de manipular o comportamento do "
                "assistente."
            )

        )

    return GuardrailResult(

        allowed=True,

        flags=flags

    )


def validate_model_output(
    answer: str
) -> GuardrailResult:

    flags = []

    normalized = answer.lower()

    for phrase in DANGEROUS_OUTPUT_PATTERNS:

        if phrase in normalized:

            flags.append(
                "unsupported_legal_certainty"
            )

    if len(answer.strip()) < 20:

        flags.append(
            "insufficient_response"
        )

    if flags:

        return GuardrailResult(

            allowed=False,

            flags=flags,

            reason=(
                "A resposta do modelo não "
                "passou pela validação."
            )

        )

    return GuardrailResult(

        allowed=True,

        flags=[]

    )