# El asistente de voz — capitulo 12

Whisper para los oidos, Piper para la voz, el modelo local para pensar.

| Pieza | Archivo | Que hace |
| --- | --- | --- |
| Agente | `agent.py` | Graba o recibe un audio, transcribe, responde y lee la respuesta. |
| VAD | `vad.py` | Detecta el fin de turno: para cuando dejas de hablar, en vez de cortar a los N segundos. |

Variables del `.env`: `WHISPER_MODEL`, `OLLAMA_MODEL`, `PIPER_VOICE`,
`VAD_BACKEND`, `VAD_SILENCE_MS`.

Ejecutar: `python agents/09_voice_assistant/agent.py [grabacion.wav]`
(sin argumento graba del microfono).

## Captura: VAD primero, ventana fija como respaldo

`record()` intenta capturar con `vad.record_turn()`, que escucha hasta que
detecta silencio suficiente. Dos detectores:

* `VAD_BACKEND=webrtc` — el detector de WebRTC (`webrtcvad-wheels`), entrenado
  para distinguir voz de ruido. Es el que aguanta un ventilador o trafico.
* `VAD_BACKEND=energy` — umbral de energia, sin dependencias, que se **calibra
  con el ruido real de tu sala** en los primeros 400 ms.

`VAD_SILENCE_MS` (700 por defecto) es el silencio que hay que oir para dar el
turno por cerrado. Es latencia pura: bajarlo responde antes pero corta frases
con pausas; subirlo es mas seguro y mas lento.

La captura necesita `sounddevice`, que a su vez necesita **PortAudio del
sistema** (`apt install libportaudio2` / `brew install portaudio`). Si falta,
el agente lo dice y cae a la ventana fija de 5 segundos con `sox` o `arecord`,
que no depende de nada instalado por pip.

## Por que Piper y no Coqui

El capitulo presenta la sintesis neuronal de extremo a extremo, y Coqui TTS
fue durante anos el paquete de referencia en Python. **La empresa Coqui cerro
en 2024**: el repositorio sigue bajo licencia abierta y hay forks activos, pero
ya no hay mantenimiento oficial, y los pesos de XTTS-v2 se publican bajo una
licencia propia de uso no comercial, que no encaja con un libro cuyos lectores
procesan facturas y correo de clientes.

Piper cubre el mismo hueco con mejor estado de conservacion: lo mantiene la
Open Home Foundation, corre en CPU —dejando la GPU para Whisper y el modelo de
lenguaje—, sus voces son ficheros ONNX de decenas de megabytes y hay varias en
espanol (es_ES, es_MX, es_AR) bajo licencia MIT.

Cambiarlo por Coqui, si lo prefieres, es sustituir la funcion `speak()`: recibe
un texto y devuelve `True` si sono. Nada mas del agente depende del motor.

Instalar Piper: `pip install piper-tts`, despues
`python3 -m piper.download_voices es_ES-davefx-medium`, y apunta `PIPER_VOICE`
al archivo `.onnx` descargado.

## Pruebas

```bash
python tests/test_vad.py    # 19 comprobaciones de la deteccion de turno
```

Las pruebas del VAD usan audio sintetico (silencio, ruido de ventilador y voz
con formantes), asi que corren sin microfono ni PortAudio. Lo que **no** esta
probado en este repositorio es la captura real desde un microfono ni la
reproduccion con Piper: el servidor de pruebas es headless y no tiene ni
tarjeta de sonido ni PortAudio instalable. Ver `docs/PRUEBAS.md`.
