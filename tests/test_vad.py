import importlib, math, random, struct, sys, time
from pathlib import Path
R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
v = importlib.import_module("agents.09_voice_assistant.vad")
res=[]; ok=lambda c,t:(print(("  PASA  " if c else "  FALLA ")+t), res.append(c))[1]
random.seed(7)

def pcm(ms, kind):
    """Genera PCM 16k mono: 'silencio', 'ruido' (ventilador) o 'voz'."""
    n = v.SAMPLE_RATE * ms // 1000
    out = []
    for i in range(n):
        t = i / v.SAMPLE_RATE
        if kind == "silencio":  s = random.gauss(0, 12)
        elif kind == "ruido":   s = random.gauss(0, 260)
        else:  # voz: armonicos con formantes y envolvente silabica
            env = 0.55 + 0.45 * math.sin(2*math.pi*4.2*t)
            s = env * 7000 * (math.sin(2*math.pi*127*t) + 0.6*math.sin(2*math.pi*381*t)
                              + 0.35*math.sin(2*math.pi*762*t) + 0.2*math.sin(2*math.pi*2400*t))
            s += random.gauss(0, 140)
        out.append(max(-32768, min(32767, int(s))))
    return struct.pack(f"<{n}h", *out)

print("== 1. rms distingue silencio, ruido y voz ==")
r = {k: v.rms(pcm(300,k)[:v.FRAME_BYTES]) for k in ("silencio","ruido","voz")}
print("   rms:", {k: round(x) for k,x in r.items()})
ok(r["silencio"] < r["ruido"] < r["voz"], "rms ordena silencio < ruido < voz")

print("\n== 2. EnergyVAD se calibra con el ruido real de la sala ==")
e_quieto = v.EnergyVAD.calibrated(pcm(1000,"silencio"))
e_ruidoso = v.EnergyVAD.calibrated(pcm(1000,"ruido"))
print(f"   umbral en sala silenciosa: {e_quieto.threshold:.0f} | con ventilador: {e_ruidoso.threshold:.0f}")
ok(e_ruidoso.threshold > e_quieto.threshold, "sube el umbral cuando hay ruido de fondo")
ok(e_quieto.is_speech(pcm(60,"voz")[:v.FRAME_BYTES]), "detecta voz")
ok(not e_quieto.is_speech(pcm(60,"silencio")[:v.FRAME_BYTES]), "no confunde silencio con voz")
ok(not e_ruidoso.is_speech(pcm(60,"ruido")[:v.FRAME_BYTES]), "calibrado, ignora el ventilador")
ok(e_ruidoso.is_speech(pcm(60,"voz")[:v.FRAME_BYTES]), "y sigue detectando voz")

print("\n== 3. WebRtcVAD funciona (paquete real) ==")
w = v.WebRtcVAD(2)
ok(w.is_speech(pcm(60,"voz")[:v.FRAME_BYTES]) in (True,False), "acepta frames de 30 ms a 16 kHz")
ok(not w.is_speech(b"\x00"*100), "rechaza un frame de tamano incorrecto")

print("\n== 4. FIN DE TURNO: voz -> silencio corta donde debe ==")
audio = pcm(1200,"voz") + pcm(1500,"silencio")
td = v.TurnDetector(v.EnergyVAD(threshold=800), silence_ms=600, max_ms=10000)
t0=time.monotonic(); r4 = td.feed_pcm(audio); dt=(time.monotonic()-t0)*1000
ok(r4 is not None and r4.reason=="silence", f"corta por silencio (razon={r4 and r4.reason})")
ok(r4 and 900 <= r4.speech_ms <= 1600, f"conserva ~1200 ms de voz: {r4 and r4.speech_ms} ms")
ok(dt < 200, f"la deteccion cuesta {dt:.0f} ms de CPU sobre 2,7 s de audio")

print("\n== 5. no corta en una pausa corta a mitad de frase ==")
audio = pcm(700,"voz") + pcm(250,"silencio") + pcm(700,"voz") + pcm(1200,"silencio")
td = v.TurnDetector(v.EnergyVAD(threshold=800), silence_ms=600)
r5 = td.feed_pcm(audio)
ok(r5 and r5.speech_ms > 1400, f"une las dos mitades: {r5 and r5.speech_ms} ms (pausa de 250 ms ignorada)")

print("\n== 6. silence_ms manda: mas corto corta antes ==")
audio = pcm(600,"voz") + pcm(400,"silencio") + pcm(600,"voz") + pcm(1500,"silencio")
corto = v.TurnDetector(v.EnergyVAD(threshold=800), silence_ms=300).feed_pcm(audio)
largo = v.TurnDetector(v.EnergyVAD(threshold=800), silence_ms=900).feed_pcm(audio)
print(f"   silence_ms=300 -> {corto.speech_ms} ms | silence_ms=900 -> {largo.speech_ms} ms")
ok(corto.speech_ms < largo.speech_ms, "el umbral de silencio decide donde se corta")

print("\n== 7. preroll: no se pierde la primera silaba ==")
audio = pcm(1000,"voz") + pcm(1200,"silencio")
sin_pre = v.TurnDetector(v.EnergyVAD(threshold=800), silence_ms=600, preroll_ms=0).feed_pcm(audio)
con_pre = v.TurnDetector(v.EnergyVAD(threshold=800), silence_ms=600, preroll_ms=300).feed_pcm(audio)
print(f"   sin preroll: {sin_pre.speech_ms} ms | con preroll: {con_pre.speech_ms} ms")
ok(con_pre.speech_ms > sin_pre.speech_ms, "el preroll recupera audio anterior a la deteccion")

print("\n== 8. solo silencio: no inventa un turno ==")
r8 = v.TurnDetector(v.EnergyVAD(threshold=800), silence_ms=600, max_ms=1500).feed_pcm(pcm(2000,"silencio"))
ok(r8 is not None and r8.reason=="no_speech" and r8.audio==b"", f"reporta no_speech (razon={r8 and r8.reason})")

print("\n== 9. monologo: corta por max_ms y no crece sin limite ==")
r9 = v.TurnDetector(v.EnergyVAD(threshold=800), silence_ms=600, max_ms=1000).feed_pcm(pcm(4000,"voz"))
ok(r9 is not None and r9.reason=="max_duration" and r9.speech_ms<=1100,
   f"corta a los {r9 and r9.speech_ms} ms por max_duration")

print("\n== 10. el turno se guarda como WAV que Whisper puede leer ==")
audio = pcm(900,"voz") + pcm(1200,"silencio")
r10 = v.TurnDetector(v.EnergyVAD(threshold=800), silence_ms=600).feed_pcm(audio)
p = v.write_wav(Path("/tmp/turno.wav"), r10.audio)
leido = v.read_wav(p)
import wave
with wave.open(str(p)) as h:
    ok(h.getframerate()==16000 and h.getnchannels()==1 and h.getsampwidth()==2,
       "WAV 16 kHz mono 16 bits, que es lo que Whisper espera")
ok(leido == r10.audio, f"ida y vuelta sin perdida ({len(leido)} bytes)")

print("\n== 11. sounddevice: import diferido, el modulo no lo exige ==")
try:
    v.record_turn(); ok(False,"deberia fallar sin PortAudio")
except OSError as e:
    ok("PortAudio" in str(e), f"solo falla al capturar de verdad: {str(e)[:60]}")
except ImportError as e:
    ok(True, f"solo falla al capturar: {e}")

print(f"\n== RESULTADO: {sum(res)}/{len(res)} ==")
sys.exit(0 if all(res) else 1)
