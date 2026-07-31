"""Mail clerk (chapter 6): IMAP triage that reads without touching.

Conecta en modo readonly (el servidor no marca nada como leido), clasifica
los correos no leidos y, si se pide, deja un BORRADOR en la carpeta Drafts.
Regla de oro del capitulo: el agente NUNCA envia correos.
"""
import email.message
import imaplib
import os
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path

import ollama
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.base_agent import BaseAgent  # noqa: E402

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
# El Anexo A usa IMAP_SERVER; el Anexo B, IMAP_HOST. Se aceptan ambos.
IMAP_SERVER = os.getenv("IMAP_SERVER") or os.getenv("IMAP_HOST", "")
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def connect() -> imaplib.IMAP4_SSL:
    connection = imaplib.IMAP4_SSL(IMAP_SERVER)
    connection.login(IMAP_USER, IMAP_PASSWORD)
    connection.select("INBOX", readonly=True)
    return connection


def fetch_unseen_headers(connection) -> list[dict]:
    _, data = connection.search(None, "UNSEEN")
    message_ids = data[0].split()
    messages = []
    for message_id in message_ids:
        _, headers_data = connection.fetch(
            message_id,
            "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])",
        )
        headers = BytesParser(policy=policy.default).parsebytes(headers_data[0][1])
        messages.append({
            "id": message_id,
            "sender": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
        })
    return messages


def classify(message: dict) -> str:
    prompt = load_prompt("mail_classify.txt").format(
        sender=message["sender"], subject=message["subject"])
    label = ollama.generate(model=MODEL, prompt=prompt)["response"].strip().lower()
    allowed = ("urgente", "responder", "informativo", "promocion")
    return label if label in allowed else "informativo"


def fetch_body(connection, message_id) -> str:
    _, msg_data = connection.fetch(message_id, "(BODY.PEEK[])")
    raw = msg_data[0][1]
    message = BytesParser(policy=policy.default).parsebytes(raw)
    body = message.get_body(preferencelist=("plain",))
    return body.get_content() if body else ""


def save_draft(connection, original: dict, body_text: str) -> None:
    # Borrador en Drafts: el usuario revisa y decide si enviar (regla de oro)
    draft = email.message.EmailMessage()
    draft["Subject"] = "Re: " + original["subject"]
    draft["To"] = original["sender"]
    draft.set_content(body_text)
    connection.append("Drafts", "", None, draft.as_bytes())


def main() -> int:
    if not (IMAP_SERVER and IMAP_USER and IMAP_PASSWORD):
        print("Faltan IMAP_SERVER / IMAP_USER / IMAP_PASSWORD en el .env "
              "(Anexo A, campo a campo; errores comunes en el Anexo B).")
        return 1
    connection = connect()
    messages = fetch_unseen_headers(connection)
    if not messages:
        print("No hay correos sin leer.")
        return 0
    print(f"{len(messages)} correos sin leer:\n")
    for index, message in enumerate(messages, 1):
        label = classify(message)
        print(f"  {index:2}. [{label:11}] {message['sender'][:35]:35} "
              f"{message['subject'][:45]}")
    choice = input("\nNumero para redactar un BORRADOR de respuesta "
                   "(Enter para salir): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(messages):
        original = messages[int(choice) - 1]
        body = fetch_body(connection, original["id"])
        prompt = load_prompt("mail_draft.txt").format(
            sender=original["sender"], subject=original["subject"],
            body=body[:2000])
        reply = ollama.generate(model=MODEL, prompt=prompt)["response"].strip()
        save_draft(connection, original, reply)
        print("Borrador guardado en Drafts. Nada se ha enviado.")
    connection.logout()
    return 0

# ---------------------------------------------------------------------------
# El patron del capitulo 3: este agente expuesto como herramientas
# ---------------------------------------------------------------------------

def tool_list_unseen(limit: int = 10) -> str:
    connection = connect()
    try:
        mensajes = fetch_unseen_headers(connection)[: int(limit)]
        if not mensajes:
            return "No hay mensajes sin leer."
        return "\n".join(
            f"[{m['id'].decode() if isinstance(m['id'], bytes) else m['id']}] "
            f"{m['sender']} — {m['subject']} — {classify(m)}"
            for m in mensajes)
    finally:
        connection.logout()


def tool_draft_reply(message_id: str, instruction: str = "") -> str:
    connection = connect()
    try:
        cuerpo = fetch_body(connection, message_id.encode())
        prompt = load_prompt("mail_draft.txt").format(
            subject="(ver mensaje)", sender="", body=cuerpo[:4000])
        if instruction:
            prompt += f"\n\nIndicacion adicional: {instruction}"
        borrador = ollama.generate(model=MODEL, prompt=prompt)["response"].strip()
        return "BORRADOR (no enviado):\n" + borrador
    finally:
        connection.logout()


class MailClerkAgent(BaseAgent):
    """Capitulo 6 sobre el patron del capitulo 3."""

    system_prompt = (
        "Ayudas con el triaje del correo. Lees y clasificas, y puedes redactar "
        "borradores. NUNCA envias nada: el envio lo hace la persona desde su "
        "cliente de correo. Dilo siempre que entregues un borrador."
    )
    tools = {
        "list_unseen": {
            "description": "Lista los mensajes sin leer con su clasificacion",
            "params": {"limit": "cuantos mensajes como maximo"},
            "func": tool_list_unseen,
        },
        "draft_reply": {
            "description": "Redacta un borrador de respuesta, sin enviarlo",
            "params": {"message_id": "identificador IMAP del mensaje",
                       "instruction": "que se quiere decir en la respuesta"},
            "func": tool_draft_reply,
        },
    }


if __name__ == "__main__":
    sys.exit(main())
