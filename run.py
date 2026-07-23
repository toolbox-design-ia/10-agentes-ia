#!/usr/bin/env python3
"""Entry point menu — launch any agent without editing code (book Annex A)."""
import importlib
import sys

AGENTS = [
    ("Second brain (RAG over your documents)", "agents.01_second_brain.agent"),
    ("Librarian (file organizer, dry-run first)", "agents.02_librarian.agent"),
    ("Mail clerk (IMAP triage, never sends alone)", "agents.03_mail_clerk.agent"),
    ("Meeting notes (Whisper -> minutes)", "agents.04_meeting_notes.agent"),
    ("Invoice reader (local vision -> CSV)", "agents.05_invoice_reader.read_invoices"),
    ("Web watcher (scrape + change alerts)", "agents.06_web_watcher.agent"),
    ("Researcher (multi-step, cited sources)", "agents.07_researcher.agent"),
    ("Code copilot (editor + local models)", "agents.08_code_copilot.agent"),
    ("Voice assistant (Whisper + Piper)", "agents.09_voice_assistant.agent"),
    ("The team (MCP orchestrator)", "agents.10_orchestrator.agent"),
]


def launch(module_name: str) -> int:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        # Dependencia sin instalar: el Anexo B explica este error paso a paso
        print(f"\nFalta un paquete: {exc.name}")
        print("Activa el entorno virtual e instala las dependencias:")
        print("  source .venv/bin/activate  (Windows: .venv\\Scripts\\activate)")
        print("  pip install -r requirements.txt")
        print("Si el error persiste, revisa el Anexo B del libro.")
        return 1
    # Los argumentos tras el numero del agente se pasan al agente tal cual
    return module.main()


def main() -> int:
    # Menu sencillo: numero -> agente. Cada agente valida sus requisitos
    # (modelo, credenciales) antes de arrancar y explica que le falta.
    print("\n10 agentes de IA — menú del libro\n")
    for i, (name, _) in enumerate(AGENTS, 1):
        print(f"  {i:2}. {name}")
    choice = input("\nElige un agente (1-10, Enter para salir): ").strip()
    if not choice:
        return 0
    try:
        name, module = AGENTS[int(choice) - 1]
    except (ValueError, IndexError):
        print("Opción no válida.")
        return 1
    print(f"\n[{name}]\n")
    return launch(module)


if __name__ == "__main__":
    sys.exit(main())
