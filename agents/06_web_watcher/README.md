# El vigia de la web — capitulo 9

Scrape responsable (robots.txt, User-Agent honesto, backoff) + clasificador
local que separa senal de ruido antes de notificar. Los nombres de las
funciones siguen exactamente los fragmentos impresos en el capitulo.

Variables del .env: OLLAMA_MODEL, OLLAMA_HOST

Ejecutar: python agents/06_web_watcher/agent.py URL "criterio"
La primera ejecucion guarda el estado; las siguientes comparan.
