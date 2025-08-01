import fitz  # PyMuPDF
import os
from PIL import Image
from io import BytesIO
from uuid import uuid4

CHUNK_HEIGHT = 3000
DPI = 150

def search_pdfs(folder_path, query):
    results = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".pdf"):
                continue
            path = os.path.join(root, file)
            try:
                doc = fitz.open(path)
                for page_num, page in enumerate(doc):
                    text = page.get_text()
                    if query.lower() in text.lower():
                        results.append((path, os.path.basename(path), page_num, text))
            except Exception as e:
                print(f"Error reading {path}: {e}")
    return results

def render_pdf_page_as_images(pdf_path, page_num, output_folder=None):
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num)

    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pix = page.get_pixmap(matrix=mat)

    full_image_path = os.path.join(output_folder or "output", "full_page.png")
    os.makedirs(os.path.dirname(full_image_path), exist_ok=True)
    pix.save(full_image_path)

    # Split image into chunks if it's too tall
    from PIL import Image
    img = Image.open(full_image_path)
    width, height = img.size

    parts = []
    for i in range(0, height, CHUNK_HEIGHT):
        box = (0, i, width, min(i + CHUNK_HEIGHT, height))
        part = img.crop(box)
        part_path = os.path.join(output_folder or "output", f"chunk_{i}.png")
        part.save(part_path)
        parts.append(part_path)

    return parts