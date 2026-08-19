import io
import re
import uuid

from pathlib import Path

from pypdf import PdfReader


def extract_pdf(
    content: bytes
):

    reader = PdfReader(
        io.BytesIO(content)
    )

    pages = []

    for index, page in enumerate(
        reader.pages,
        start=1
    ):

        try:

            text = (
                page.extract_text()
                or ""
            )

        except Exception:

            text = ""

        pages.append({

            "page": index,

            "text": text

        })

    full_text = "\n".join(

        page["text"]

        for page in pages

    )

    return {

        "pages": pages,

        "text": full_text,

        "page_count": len(pages)

    }


def clean_pdf_text(
    text: str
) -> str:

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def create_document_id():

    return (
        "doc_"
        + uuid.uuid4().hex[:12]
    )