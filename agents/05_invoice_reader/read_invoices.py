"""Invoice reader (chapter 8): from photo or PDF to validated CSV.

Uso impreso en el capitulo:
    python read_invoices.py --folder ./invoices --output invoices.csv

PDFs con texto se leen con pdfplumber; imagenes, con un modelo de vision
local. La validacion aritmetica (impresa en el capitulo) es la red de
seguridad: nunca confiar a ciegas en el modelo.
"""
import argparse
import csv
import json
import re
import os
import sys
from pathlib import Path

import ollama
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.base_agent import BaseAgent  # noqa: E402

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llama3.2-vision:11b")

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

EXTRACT_PROMPT = """Extrae los datos de esta factura y responde UNICAMENTE con
un objeto JSON valido con esta forma exacta (sin texto alrededor, sin markdown):
{"supplier": str, "invoice_number": str o null, "date": str,
 "items": [{"description": str, "quantity": num, "unit_price": num, "amount": num}],
 "subtotal": num, "tax_rate": num, "tax_amount": num, "total": num}
"""


class Item(BaseModel):
    description: str
    quantity: float
    unit_price: float
    amount: float


class Invoice(BaseModel):
    supplier: str
    invoice_number: str | None
    date: str
    items: list[Item]
    subtotal: float
    tax_rate: float
    tax_amount: float
    total: float


def validate_invoice(invoice: Invoice) -> list[str]:
    errors = []
    items_sum = sum(item.amount for item in invoice.items)
    if abs(items_sum - invoice.subtotal) > 0.05:
        errors.append("Items sum does not match subtotal")
    calculated_total = invoice.subtotal + invoice.tax_amount
    if abs(calculated_total - invoice.total) > 0.05:
        errors.append("Subtotal plus tax does not match total")
    return errors


def extract_json(raw_text: str) -> dict:
    # Anexo B: busca el primer bloque que empieza en { y termina en el } final
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError("no se encontro un bloque JSON en la respuesta")
    return json.loads(match.group(0))


def read_pdf_text(path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def model_response(path: Path) -> str:
    if path.suffix.lower() in IMAGE_SUFFIXES:
        reply = ollama.chat(model=VISION_MODEL, messages=[{
            "role": "user", "content": EXTRACT_PROMPT,
            "images": [str(path)],
        }])
        return reply["message"]["content"]
    text = read_pdf_text(path)
    return ollama.generate(model=MODEL,
                           prompt=EXTRACT_PROMPT + "\n\nFactura:\n" + text[:6000],
                           )["response"]


def process_folder(folder: Path, output: Path) -> tuple[int, int]:
    processed = failed = 0
    with open(output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file", "supplier", "invoice_number", "date",
                         "subtotal", "tax_amount", "total", "warnings"])
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in IMAGE_SUFFIXES | {".pdf"}:
                continue
            try:
                invoice = Invoice(**extract_json(model_response(path)))
                warnings = validate_invoice(invoice)
                writer.writerow([path.name, invoice.supplier,
                                 invoice.invoice_number or "", invoice.date,
                                 invoice.subtotal, invoice.tax_amount,
                                 invoice.total, "; ".join(warnings)])
                status = "AVISO: " + "; ".join(warnings) if warnings else "ok"
                print(f"  {path.name}: {status}")
                processed += 1
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                print(f"  {path.name}: ERROR ({exc}) — revisa el Anexo B")
                failed += 1
    return processed, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Lector de facturas local")
    parser.add_argument("--folder", default="./invoices",
                        help="carpeta con PDFs o fotos de facturas")
    parser.add_argument("--output", default="invoices.csv",
                        help="CSV de salida")
    args = parser.parse_args()
    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"No existe la carpeta {folder}")
        return 1
    processed, failed = process_folder(folder, Path(args.output))
    print(f"\nProcesadas: {processed} | Con error: {failed} "
          f"| CSV: {args.output}")
    return 0 if failed == 0 else 1

# ---------------------------------------------------------------------------
# El patron del capitulo 3: este agente expuesto como herramientas
# ---------------------------------------------------------------------------

def tool_read_invoice(path: str) -> str:
    archivo = Path(path)
    if not archivo.is_file():
        return f"No existe el archivo {archivo}."
    datos = Invoice(**extract_json(model_response(archivo)))
    avisos = validate_invoice(datos)
    return (f"proveedor={datos.supplier} fecha={datos.date} "
            f"subtotal={datos.subtotal} impuesto={datos.tax_amount} "
            f"total={datos.total} avisos={avisos or 'ninguno'}")


def tool_process_folder(folder: str, output: str = "invoices.csv") -> str:
    ok, pendientes = process_folder(Path(folder), Path(output))
    return f"Procesadas {ok} facturas; {pendientes} marcadas para revision. CSV: {output}"


class InvoiceReaderAgent(BaseAgent):
    """Capitulo 8 sobre el patron del capitulo 3."""

    system_prompt = (
        "Extraes datos de facturas con un modelo de vision local. Nunca "
        "inventes una cifra: si un campo no se lee con confianza, dilo. "
        "Avisa siempre de que los importes deben revisarse antes de usarlos."
    )
    tools = {
        "read_invoice": {
            "description": "Lee una factura (imagen o PDF) y devuelve sus campos",
            "params": {"path": "ruta de la imagen o PDF"},
            "func": tool_read_invoice,
        },
        "process_folder": {
            "description": "Procesa una carpeta de facturas y escribe un CSV",
            "params": {"folder": "carpeta con las facturas",
                       "output": "ruta del CSV de salida"},
            "func": tool_process_folder,
        },
    }


if __name__ == "__main__":
    sys.exit(main())
