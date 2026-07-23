# El lector de facturas — capitulo 8

De la foto o el PDF al CSV validado. La validacion aritmetica impresa en el
capitulo es la red de seguridad: nunca confiar a ciegas en el modelo.

Variables del .env: OLLAMA_MODEL, OLLAMA_VISION_MODEL (para imagenes;
descargalo con: ollama pull llama3.2-vision:11b — ver tabla de VRAM, cap. 2)

Ejecutar (comando impreso en el capitulo):
  python read_invoices.py --folder ./invoices --output invoices.csv
