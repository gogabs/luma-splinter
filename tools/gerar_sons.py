#!/usr/bin/env python3
"""Gera os sons curtos do leitor (bipes) em sounds/. Só biblioteca padrão."""
import math
import os
import struct
import wave

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sounds")
RATE = 44100


def tom(nome, notas, volume=0.35):
    """notas: lista de (frequência, segundos)."""
    quadros = []
    for freq, dur in notas:
        n = int(RATE * dur)
        for i in range(n):
            env = min(1.0, i / 200, (n - i) / 400)
            quadros.append(volume * env * math.sin(2 * math.pi * freq * i / RATE))
    os.makedirs(OUT, exist_ok=True)
    with wave.open(os.path.join(OUT, nome + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, q)) * 32767)) for q in quadros))


tom("pausa", [(660, 0.07), (440, 0.1)])
tom("retoma", [(440, 0.07), (660, 0.1)])
tom("marca", [(880, 0.06), (1175, 0.12)])
tom("borda", [(220, 0.12)])
tom("capitulo", [(523, 0.08), (659, 0.08), (784, 0.12)])
tom("menu_mover", [(600, 0.04)])
tom("menu_confirmar", [(800, 0.05), (1000, 0.07)])
