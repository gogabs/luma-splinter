"""Roda o main.py inteiro, sem console: aperta botões e confere que nada quebra."""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
RAIZ = os.path.join(AQUI, "..")
SDK = os.path.join(RAIZ, "..", "r36s-a11y-sdk", "python")


@unittest.skipUnless(os.path.isdir(os.path.join(RAIZ, "r36s_a11y")) or os.path.isdir(SDK),
                     "sem o Mage Core por perto")
class Fumaca(unittest.TestCase):
    def test_fluxo(self):
        from test_leitor import faz_epub
        with tempfile.TemporaryDirectory() as livros, tempfile.TemporaryDirectory() as saves:
            faz_epub(livros)
            os.environ.update(A11Y_LIVROS=livros, A11Y_SAVE_DIR=saves, A11Y_FALA_DESLIGADA=__file__)
            sys.path.insert(0, RAIZ)
            sys.path.insert(1, SDK)
            import r36s_a11y as a11y
            ditos = []
            a11y.Game.run = lambda self: None
            src = open(os.path.join(RAIZ, "main.py"), encoding="utf-8").read()
            ns = {"__name__": "main_teste", "__file__": os.path.join(RAIZ, "main.py")}
            exec(compile(src, "main.py", "exec"), ns)
            game = ns["game"]
            game.say = lambda t, queue=False, on_done=None: ditos.append(t)
            for fn in game._handlers["start"]:
                fn()
            self.assertIn("Seus livros", ditos[-1])
            press = lambda b: game._dispatch_button(b, a11y.DOWN, 0)
            press("b")                       # abre o livro
            self.assertIn("Livro Teste", ditos[-1])
            press("b")                       # começar a ler
            self.assertTrue(ns["ctx"]["leitura"].tocando)
            press("r1")
            press("r2")
            self.assertIn("Velocidade mais 1", " ".join(ditos))
            press("x")
            press("b")                       # pausa
            self.assertFalse(ns["ctx"]["leitura"].tocando)
            press("start")                   # menu do livro
            press("down"); press("down"); press("b")   # marcadores
            self.assertIn("Marcadores", ditos[-1])
            press("b")                       # vai ao marcador e lê
            self.assertTrue(ns["ctx"]["leitura"].tocando)
            press("a")                       # volta aos livros
            self.assertIn("Seus livros", ditos[-1])
            self.assertTrue(os.path.exists(os.path.join(saves, "progresso.json")))


if __name__ == "__main__":
    unittest.main()
