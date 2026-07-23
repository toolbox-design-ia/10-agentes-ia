# Segundo cerebro privado — capitulo 4

RAG local sobre tus notas (.md/.txt): indexa con embeddings de Ollama en
ChromaDB y responde citando fragmentos. Nada sale de tu maquina.

Variables del .env: NOTES_DIR, OLLAMA_MODEL, OLLAMA_EMBED_MODEL
(descarga el modelo de embeddings con: ollama pull nomic-embed-text)

Ejecutar: python run.py (opcion 1)  |  python agents/01_second_brain/agent.py
Reindexar tras cambiar notas: anade --reindex
