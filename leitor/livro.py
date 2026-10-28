"""O livro como lista de capítulos > parágrafos > frases, e o cursor que anda por ele."""
import hashlib
import os

from .epub import Epub
from .texto import extract, sentences


class Capitulo:
    def __init__(self, titulo, paragrafos):
        self.titulo = titulo
        self.paragrafos = paragrafos        # lista de listas de frases
        self.chars = sum(len(s) for p in paragrafos for s in p)


class Livro:
    """Posição = (capítulo, parágrafo, frase), tudo a partir do zero."""

    def __init__(self, titulo, autor, capitulos, ident=""):
        self.titulo, self.autor, self.capitulos, self.ident = titulo, autor, capitulos, ident
        self._antes = []
        total = 0
        for c in capitulos:
            self._antes.append(total)
            total += c.chars
        self.total = max(total, 1)

    @classmethod
    def abrir(cls, caminho):
        ep = Epub(caminho)
        capitulos = []
        for name in ep.spine:
            try:
                titulo_h, paras = extract(ep.read(name))
            except KeyError:
                continue
            frases = [sentences(p) for p in paras]
            frases = [f for f in frases if f]
            if not frases:
                continue
            titulo = ep.toc.get(name) or titulo_h
            capitulos.append(Capitulo(titulo, frases))
        if not capitulos:
            raise ValueError("Este livro não tem texto que eu consiga ler.")
        for i, c in enumerate(capitulos, 1):
            if not c.titulo:
                c.titulo = "Capítulo %d" % i
        base = os.path.basename(caminho)
        titulo = ep.title or os.path.splitext(base)[0]
        return cls(titulo, ep.author, capitulos, identificador(caminho))

    # --- consulta ------------------------------------------------------
    def frase(self, pos):
        c, p, s = pos
        return self.capitulos[c].paragrafos[p][s]

    def valida(self, pos):
        try:
            c, p, s = pos
            return 0 <= s < len(self.capitulos[c].paragrafos[p]) and c >= 0 and p >= 0 and s >= 0
        except (IndexError, TypeError, ValueError):
            return False

    def percentual(self, pos):
        c, p, s = pos
        cap = self.capitulos[c]
        feito = self._antes[c] + sum(len(x) for q in cap.paragrafos[:p] for x in q) \
            + sum(len(x) for x in cap.paragrafos[p][:s])
        return min(100, int(100 * feito / self.total))

    def posicao_de_percentual(self, pct):
        alvo = self.total * max(0, min(99, pct)) / 100
        c = max(i for i, a in enumerate(self._antes) if a <= alvo)
        resto = alvo - self._antes[c]
        for p, frases in enumerate(self.capitulos[c].paragrafos):
            tam = sum(len(x) for x in frases)
            if resto < tam:
                return (c, p, 0)
            resto -= tam
        return (c, len(self.capitulos[c].paragrafos) - 1, 0)

    def trecho(self, ini, fim, limite=5000):
        """Texto de ini até fim (inclusive), parágrafos separados por linha em branco; None se passar do limite."""
        partes, pos, atual = [], ini, None
        while pos is not None:
            if atual is not None and pos[:2] != atual:
                partes.append("\n\n")
            elif atual is not None:
                partes.append(" ")
            atual = pos[:2]
            partes.append(self.frase(pos))
            if pos == fim:
                break
            pos = self.proxima_frase(pos)
            if sum(len(p) for p in partes) > limite:
                return None
        return "".join(partes)

    def contar(self, ini, fim):
        """Quantas frases há de ini a fim, inclusive."""
        n, pos = 1, ini
        while pos is not None and pos != fim:
            pos = self.proxima_frase(pos)
            n += 1
        return n

    def descricao(self, pos):
        c, p, _ = pos
        cap = self.capitulos[c]
        return "%s, parágrafo %d de %d, %d%% do livro" % (cap.titulo, p + 1, len(cap.paragrafos),
                                                         self.percentual(pos))

    # --- navegação (devolvem None quando não há para onde ir) ----------
    def proxima_frase(self, pos):
        c, p, s = pos
        if s + 1 < len(self.capitulos[c].paragrafos[p]):
            return (c, p, s + 1)
        return self.proximo_paragrafo(pos)

    def frase_anterior(self, pos):
        c, p, s = pos
        if s > 0:
            return (c, p, s - 1)
        if p > 0:
            return (c, p - 1, len(self.capitulos[c].paragrafos[p - 1]) - 1)
        if c > 0:
            ant = self.capitulos[c - 1].paragrafos
            return (c - 1, len(ant) - 1, len(ant[-1]) - 1)
        return None

    def proximo_paragrafo(self, pos):
        c, p, _ = pos
        if p + 1 < len(self.capitulos[c].paragrafos):
            return (c, p + 1, 0)
        if c + 1 < len(self.capitulos):
            return (c + 1, 0, 0)
        return None

    def paragrafo_anterior(self, pos):
        """Do meio do parágrafo volta ao começo dele; do começo, ao parágrafo de trás."""
        c, p, s = pos
        if s > 0:
            return (c, p, 0)
        if p > 0:
            return (c, p - 1, 0)
        if c > 0:
            return (c - 1, len(self.capitulos[c - 1].paragrafos) - 1, 0)
        return None

    def proximo_capitulo(self, pos):
        return (pos[0] + 1, 0, 0) if pos[0] + 1 < len(self.capitulos) else None

    def capitulo_anterior(self, pos):
        c, p, s = pos
        if (p, s) != (0, 0):
            return (c, 0, 0)
        return (c - 1, 0, 0) if c > 0 else None


def identificador(caminho):
    """Mesmo livro, mesma identidade, mesmo se mudar de pasta."""
    base = os.path.basename(caminho).lower()
    try:
        tam = os.path.getsize(caminho)
    except OSError:
        tam = 0
    return hashlib.sha1(("%s|%d" % (base, tam)).encode("utf-8")).hexdigest()[:16]
