#!/usr/bin/env python3
"""Gera o zip para copiar em a11y/games no cartão: python3 tools/empacotar.py [pasta-do-sdk] [saida.zip]"""
import json
import os
import sys
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, "..")
sdk = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, "..", "r36s-a11y-sdk")
manifesto = json.load(open(os.path.join(RAIZ, "game.json"), encoding="utf-8"))
saida = sys.argv[2] if len(sys.argv) > 2 else "splinter-%s.zip" % manifesto["version"]
manifesto["id"] = "splinter"       # o id é o nome da pasta

with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("splinter/game.json", json.dumps(manifesto, ensure_ascii=False, indent=2))
    z.write(os.path.join(RAIZ, "main.py"), "splinter/main.py")
    for pasta, destino in ((os.path.join(RAIZ, "leitor"), "leitor"), (os.path.join(RAIZ, "sounds"), "sounds"),
                           (os.path.join(sdk, "python", "r36s_a11y"), "r36s_a11y")):
        for raiz, dirs, arquivos in os.walk(pasta):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for nome in arquivos:
                caminho = os.path.join(raiz, nome)
                z.write(caminho, "splinter/%s/%s" % (destino, os.path.relpath(caminho, pasta).replace(os.sep, "/")))
print(saida)
