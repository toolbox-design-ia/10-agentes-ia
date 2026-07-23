# El equipo — capitulo 13

Un modelo con tool calling nativo enruta peticiones a los demas agentes.
Cada contrato de herramienta dice tambien lo que el agente NO hace: esa es
la primera barrera de seguridad. Cada ejecucion deja traza en
traces/orquestador.jsonl.

Variables del .env: ORCHESTRATOR_MODEL (por defecto qwen2.5:14b-instruct;
ver el cuello de botella de la VRAM en el capitulo 13)

Ejecutar: python agents/10_orchestrator/agent.py "tu peticion"
