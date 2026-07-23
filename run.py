#!/usr/bin/env python3
"""Entry point menu — launch any agent without editing code (book Annex A)."""
import sys

AGENTS = [
    ("Second brain (RAG over your documents)", "agents.01_second_brain"),
    ("Librarian (file organizer, dry-run first)", "agents.02_librarian"),
    ("Mail clerk (IMAP triage, never sends alone)", "agents.03_mail_clerk"),
    ("Meeting notes (Whisper -> minutes)", "agents.04_meeting_notes"),
    ("Invoice reader (local vision -> CSV)", "agents.05_invoice_reader"),
    ("Web watcher (scrape + change alerts)", "agents.06_web_watcher"),
    ("Researcher (multi-step, cited sources)", "agents.07_researcher"),
    ("Code copilot (editor + local models)", "agents.08_code_copilot"),
    ("Voice assistant (Whisper + Piper)", "agents.09_voice_assistant"),
    ("The team (MCP orchestrator)", "agents.10_orchestrator"),
]


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
    print(f"\n[{name}] — el código de este agente se añade con su capítulo.")
    print(f"Módulo: {module} (ver la tabla capítulo → código del README)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
