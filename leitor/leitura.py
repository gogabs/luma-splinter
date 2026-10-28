"""Leitura contínua frase a frase, sem depender do jogo: recebe a função de fala.

say(texto, queue=False, on_done=None) é o Game.say. Mantém sempre algumas
frases na fila da fala para não haver pausa entre elas, e só avança a posição
quando o sintetizador termina de falar a frase (assim, ao pausar, retoma da
frase que estava no ar).
"""
from .texto import falavel

ADIANTE = 2


class Leitura:
    def __init__(self, livro, pos, say, hush, ao_fim=None, ao_mudar_capitulo=None):
        self.livro, self.pos = livro, pos
        self.say, self.hush = say, hush
        self.ao_fim = ao_fim
        self.tocando = False
        self._geracao = 0
        self._na_fila = 0
        self._cauda = None
        self._capitulo_dito = None

    # --- fala ------------------------------------------------------------
    def _texto(self, pos):
        c, p, s = pos
        texto = falavel(self.livro.frase(pos))
        cap = self.livro.capitulos[c]
        if (p, s) == (0, 0) and self._capitulo_dito != c:
            self._capitulo_dito = c
            if cap.titulo.lower() not in cap.paragrafos[0][0].lower()[:len(cap.titulo) + 20]:
                texto = "%s. %s" % (cap.titulo, texto)
        return texto

    def _enfileirar(self, pos, primeira):
        gen = self._geracao
        self._cauda = pos
        self._na_fila += 1
        self.say(self._texto(pos), queue=not primeira,
                 on_done=lambda feito, g=gen, q=pos: self._terminou(g, q, feito))

    def _encher(self):
        while self._na_fila < ADIANTE:
            prox = self.livro.proxima_frase(self._cauda)
            if prox is None:
                return
            self._enfileirar(prox, False)

    def _terminou(self, gen, pos, feito):
        if gen != self._geracao or not feito:
            return
        self._na_fila -= 1
        prox = self.livro.proxima_frase(pos)
        if prox is None:
            self.tocando = False
            if self.ao_fim:
                self.ao_fim()
            return
        self.pos = prox
        self._encher()

    # --- controles -------------------------------------------------------
    def texto_atual(self):
        """O que seria falado agora (com o título, se for começo de capítulo)."""
        self._capitulo_dito = None
        return self._texto(self.pos)

    def tocar(self, depois_do_que_esta_falando=False):
        """Fala a partir da posição. Com True, entra na fila em vez de cortar um aviso."""
        self._geracao += 1
        self.tocando = True
        self._na_fila = 0
        self._capitulo_dito = None
        self._enfileirar(self.pos, not depois_do_que_esta_falando)
        self._encher()

    def interromper(self):
        """Corta a fala na hora, sem mexer na posição: quem chama retoma da frase em curso."""
        self._geracao += 1
        self._na_fila = 0
        self.hush()

    def pausar(self):
        self._geracao += 1
        self.tocando = False
        self.hush()

    def ir_para(self, pos, tocar=None):
        """Muda a posição. Se estava tocando, continua dali."""
        if pos is None:
            return False
        querer = self.tocando if tocar is None else tocar
        self.pos = pos
        self._capitulo_dito = None
        if querer:
            self.tocar()
        else:
            self._geracao += 1
            self.tocando = False
        return True
