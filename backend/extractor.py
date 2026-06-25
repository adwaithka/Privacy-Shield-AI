import io

import fitz
import pytesseract

from PIL import (
    Image,
    ImageFilter,
    ImageOps
)

from docx import Document


# ------------------------------------------------
# Configure Tesseract
# ------------------------------------------------

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


# ------------------------------------------------
# OCR Image Preprocessing
# ------------------------------------------------

def preprocess_image(img):

    img = img.convert("L")

    img = ImageOps.autocontrast(
        img
    )

    img = img.filter(
        ImageFilter.SHARPEN
    )

    return img


# ------------------------------------------------
# OCR
# ------------------------------------------------

def extract_image_text(image_path):

    img = Image.open(
        image_path
    )

    img = preprocess_image(
        img
    )

    text = pytesseract.image_to_string(
        img,
        lang="eng",
        config="--psm 6"
    )

    return text.strip()


# ------------------------------------------------
# PDF
# ------------------------------------------------

def extract_pdf_text(pdf_path):

    text_parts = []

    doc = fitz.open(
        pdf_path
    )

    for page in doc:

        page_text = page.get_text()

        if page_text.strip():

            text_parts.append(
                page_text
            )

            continue

        pix = page.get_pixmap(
            dpi=300
        )

        image = Image.open(
            io.BytesIO(
                pix.tobytes("png")
            )
        )

        image = preprocess_image(
            image
        )

        ocr_text = pytesseract.image_to_string(
            image,
            lang="eng",
            config="--psm 6"
        )

        text_parts.append(
            ocr_text
        )

    doc.close()

    return "\n".join(
        text_parts
    )


# ------------------------------------------------
# DOCX
# ------------------------------------------------

def extract_docx_text(docx_path):

    doc = Document(
        docx_path
    )

    text_parts = []

    for para in doc.paragraphs:

        if para.text.strip():

            text_parts.append(
                para.text
            )

    return "\n".join(
        text_parts
    )


# ------------------------------------------------
# TXT
# ------------------------------------------------

def extract_txt_text(txt_path):

    with open(
        txt_path,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as f:

        return f.read()


# ------------------------------------------------
# Main Router
# ------------------------------------------------

def extract_text(
    file_path,
    mime_type=None
):

    lower = file_path.lower()

    if lower.endswith(".pdf"):

        return extract_pdf_text(
            file_path
        )

    if lower.endswith(".docx"):

        return extract_docx_text(
            file_path
        )

    if lower.endswith(".txt"):

        return extract_txt_text(
            file_path
        )

    return extract_image_text(
        file_path
    )