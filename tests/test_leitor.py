import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from leitor.estado import Estado
from leitor.leitura import Leitura
from leitor.livro import Capitulo, Livro
from leitor.texto import extract, falavel, sentences

OPF = """<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Livro Teste</dc:title><dc:creator>Ana</dc:creator></metadata>
<manifest><item id="n" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="c1" href="t/c1.xhtml" media-type="application/xhtml+xml"/>
<item id="c2" href="t/c2.xhtml" media-type="application/xhtml+xml"/>
<item id="cv" href="t/cover.xhtml" media-type="application/xhtml+xml"/></manifest>
<spine><itemref idref="cv"/><itemref idref="c1"/><itemref idref="c2"/></spine></package>"""
NAV = """<html xmlns:epub="x"><body><nav epub:type="toc"><ol>
<li><a href="t/c1.xhtml">Primeiro dia</a></li><li><a href="t/c2.xhtml#x">Segundo dia</a></li></ol></nav></body></html>"""
C1 = "<html><head><title>x</title></head><body><h1>Primeiro dia</h1><p>Olá, mundo. O Sr. Silva chegou! Ele disse: — Bom dia.</p><p>Fim.</p></body></html>"
C2 = "<html><body><p>Segundo capítulo tem texto.</p></body></html>"


def faz_epub(pasta):
    caminho = os.path.join(pasta, "teste.epub")
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("META-INF/container.xml",
                   '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                   '<rootfile full-path="OEBPS/content.opf"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf", OPF)
        z.writestr("OEBPS/nav.xhtml", NAV)
        z.writestr("OEBPS/t/cover.xhtml", "<html><body><img src='a.png'/></body></html>")
        z.writestr("OEBPS/t/c1.xhtml", C1)
        z.writestr("OEBPS/t/c2.xhtml", C2)
    return caminho


class TextoTest(unittest.TestCase):
    def test_abreviacao_e_iniciais(self):
        self.assertEqual(sentences("O Sr. Silva chegou! Ele riu. J. R. Tolkien escreveu."),
                         ["O Sr. Silva chegou!", "Ele riu.", "J. R. Tolkien escreveu."])

    def test_frase_longa_e_dividida(self):
        s = sentences(", ".join(["palavra"] * 80))
        self.assertTrue(all(len(x) <= 151 for x in s))
        self.assertGreater(len(s), 1)

    def test_extrai_paragrafos_e_ignora_script(self):
        h, p = extract("<h1>T</h1><script>x()</script><p>a<br>b</p><p>* * *</p>")
        self.assertEqual((h, p), ("T", ["T", "a", "b"]))

    def test_falavel(self):
        self.assertEqual(falavel("— Oi, tudo bem — disse ele."), "Oi, tudo bem, disse ele.")


class LivroTest(unittest.TestCase):
    def test_abre_epub(self):
        with tempfile.TemporaryDirectory() as d:
            livro = Livro.abrir(faz_epub(d))
        self.assertEqual((livro.titulo, livro.autor), ("Livro Teste", "Ana"))
        self.assertEqual([c.titulo for c in livro.capitulos], ["Primeiro dia", "Segundo dia"])
        self.assertEqual(livro.frase((0, 0, 0)), "Primeiro dia")

    def livro(self):
        return Livro("t", "a", [Capitulo("A", [["a1", "a2"], ["b1"]]), Capitulo("B", [["c1"]])])

    def test_navegacao(self):
        l = self.livro()
        self.assertEqual(l.proxima_frase((0, 0, 1)), (0, 1, 0))
        self.assertEqual(l.proxima_frase((0, 1, 0)), (1, 0, 0))
        self.assertIsNone(l.proxima_frase((1, 0, 0)))
        self.assertEqual(l.frase_anterior((1, 0, 0)), (0, 1, 0))
        self.assertEqual(l.paragrafo_anterior((0, 0, 1)), (0, 0, 0))
        self.assertIsNone(l.paragrafo_anterior((0, 0, 0)))
        self.assertEqual(l.capitulo_anterior((1, 0, 0)), (0, 0, 0))
        self.assertEqual(l.capitulo_anterior((1, 0, 0)), (0, 0, 0))
        self.assertEqual(l.capitulo_anterior((0, 1, 0)), (0, 0, 0))
        self.assertIsNone(l.proximo_capitulo((1, 0, 0)))

    def test_percentual(self):
        l = self.livro()
        self.assertEqual(l.percentual((0, 0, 0)), 0)
        self.assertEqual(l.posicao_de_percentual(0), (0, 0, 0))
        self.assertEqual(l.posicao_de_percentual(99)[0], 1)
        self.assertTrue(l.valida((1, 0, 0)))
        self.assertFalse(l.valida((5, 0, 0)))


class EstadoTest(unittest.TestCase):
    def test_persiste(self):
        with tempfile.TemporaryDirectory() as d:
            e = Estado(d)
            e.salvar_posicao("x", (1, 2, 3))
            e.adicionar_marca("x", (0, 0, 1), "um")
            e.velocidade = 20
            e2 = Estado(d)
            self.assertEqual(e2.posicao("x"), (1, 2, 3))
            self.assertEqual(e2.marcas("x"), [((0, 0, 1), "um")])
            self.assertEqual(e2.velocidade, 20)


class FalaFalsa:
    def __init__(self):
        self.fila = []      # (texto, callback)
        self.cortes = 0

    def say(self, texto, queue=False, on_done=None):
        if not queue:
            self.fila = []
        self.fila.append((texto, on_done))

    def hush(self):
        self.fila = []
        self.cortes += 1

    def terminar_uma(self):
        texto, cb = self.fila.pop(0)
        cb(True)
        return texto


class LeituraTest(unittest.TestCase):
    def setUp(self):
        self.livro = Livro("t", "a", [Capitulo("Um", [["a1", "a2"], ["b1"]]), Capitulo("Dois", [["c1"]])])
        self.fala = FalaFalsa()
        self.fim = []
        self.l = Leitura(self.livro, (0, 0, 0), self.fala.say, self.fala.hush, ao_fim=lambda: self.fim.append(1))

    def test_le_ate_o_fim_anunciando_capitulos(self):
        self.l.tocar()
        self.assertEqual(len(self.fala.fila), 1)          # uma frase por vez
        ditos = []
        while self.fala.fila:
            ditos.append(self.fala.terminar_uma())
        self.assertEqual(ditos, ["Um. a1", "a2", "b1", "Dois. c1"])
        self.assertEqual(self.fim, [1])
        self.assertFalse(self.l.tocando)

    def test_pausa_retoma_da_frase_no_ar(self):
        self.l.tocar()
        self.fala.terminar_uma()
        self.assertEqual(self.l.pos, (0, 0, 1))
        self.l.pausar()
        self.fala.fila = []
        self.l.tocar()
        self.assertEqual(self.fala.fila[0][0], "a2")

    def test_callback_velho_e_ignorado(self):
        self.l.tocar()
        velho = self.fala.fila[0][1]
        self.l.ir_para((0, 1, 0))
        velho(True)
        self.assertEqual(self.l.pos, (0, 1, 0))
        self.assertEqual(self.fala.fila[0][0], "b1")

    def test_interromper_corta_e_ignora_callbacks_velhos(self):
        self.l.tocar()
        velho = self.fala.fila[0][1]
        self.l.interromper()
        self.assertEqual(self.fala.cortes, 1)
        velho(True)
        self.assertEqual(self.l.pos, (0, 0, 0))
        self.fala.fila = []
        self.l.tocar()                       # retoma do começo da mesma frase
        self.assertEqual(self.fala.fila[0][0], "Um. a1")

    def test_pular_parado_nao_fala(self):
        self.l.ir_para((1, 0, 0))
        self.assertEqual(self.fala.fila, [])


if __name__ == "__main__":
    unittest.main()
