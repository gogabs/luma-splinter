"""Leitura contínua frase a frase, sem depender do jogo: recebe a função de fala.

say(texto, queue=False, on_done=None) é o Game.say. Coloca uma frase por vez
na fila da fala e só encadeia a próxima quando o sintetizador termina a atual.
A posição só avança nesse momento, então ao pausar ou cortar a fala se retoma
do começo da frase que estava no ar.

Modos (ate): None lê sem parar até o fim do livro; "paragrafo" lê só o parágrafo
em curso, frase por frase, e para (navegação parada); "frase" lê só uma frase.
Em qualquer modo a saída é a mesma: uma frase de cada vez para o Core.
"""
from .texto import falavel

ADIANTE = 1
MANTER = object()


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
        self._ate = None
        self._limite = None      # (capítulo, parágrafo) do modo "paragrafo"
        self._inicio = None      # onde a leitura limitada começou

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

    @property
    def continua(self):
        """Tocando sem limite: a leitura normal, que só para no fim do livro ou ao pausar."""
        return self.tocando and self._ate is None

    def _seguinte(self, pos):
        """Próxima frase permitida pelo modo, ou None."""
        prox = self.livro.proxima_frase(pos)
        if prox is None or self._ate is None:
            return prox
        if self._ate == "frase" or prox[:2] != self._limite:
            return None
        return prox

    def _encher(self):
        while self._na_fila < ADIANTE:
            prox = self._seguinte(self._cauda)
            if prox is None:
                return
            self._enfileirar(prox, False)

    def _terminou(self, gen, pos, feito):
        if gen != self._geracao or not feito:
            return
        self._na_fila -= 1
        prox = self._seguinte(pos)
        if prox is None:
            self.tocando = False
            if self._ate is not None:             # acabou o trecho pedido; fica parado no começo dele
                self.pos = self._inicio
                self._ate = None
            elif self.livro.proxima_frase(pos) is None and self.ao_fim:
                self.ao_fim()
            return
        self.pos = prox
        self._encher()

    # --- controles -------------------------------------------------------
    def texto_atual(self):
        """O que seria falado agora (com o título, se for começo de capítulo)."""
        self._capitulo_dito = None
        return self._texto(self.pos)

    def tocar(self, depois_do_que_esta_falando=False, ate=MANTER):
        """Fala a partir da posição. Com True, entra na fila em vez de cortar um aviso.

        ate: None (sem limite), "paragrafo" ou "frase"; sem informar, mantém o modo atual."""
        if ate is not MANTER:
            self._ate = ate
        self._limite = self.pos[:2]
        self._inicio = self.pos if self._ate == "frase" else (self.pos[0], self.pos[1], 0)
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
        self._ate = None
        self.hush()

    def ir_para(self, pos, tocar=None, ate=None):
        """Muda a posição. Sem tocar=, continua do jeito que estava (parado ou lendo)."""
        if pos is None:
            return False
        querer = self.tocando if tocar is None else tocar
        self.pos = pos
        self._capitulo_dito = None
        if querer:
            self.tocar(ate=ate)
        else:
            self._geracao += 1
            self.tocando = False
            self._ate = None
        return True
