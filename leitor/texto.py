"""Do HTML de um capítulo para parágrafos e frases faladas."""
import re
from html.parser import HTMLParser

BLOCKS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr",
          "br", "section", "article", "pre", "dt", "dd", "figcaption", "caption", "ul", "ol", "table", "hr"}
SKIP = {"script", "style", "head", "svg", "math"}


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paras = []
        self.heading = ""
        self._buf = []
        self._skip = 0
        self._in_heading = False
        self._heading_buf = []

    def _flush(self):
        text = " ".join("".join(self._buf).split())
        self._buf = []
        if re.search(r"\w", text):
            self.paras.append(text)

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self._skip += 1
        if self._skip:
            return
        if tag in BLOCKS:
            self._flush()
        if tag in ("h1", "h2", "h3") and not self.heading:
            self._in_heading, self._heading_buf = True, []
        if tag == "img":
            alt = " ".join((dict(attrs).get("alt") or "").split())
            if len(alt) > 3:
                self._buf.append(" Imagem: %s. " % alt.rstrip("."))

    def handle_endtag(self, tag):
        if tag in SKIP and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag in BLOCKS:
            self._flush()
        if self._in_heading and tag in ("h1", "h2", "h3"):
            self._in_heading = False
            self.heading = " ".join("".join(self._heading_buf).split())

    def handle_data(self, data):
        if self._skip:
            return
        self._buf.append(data)
        if self._in_heading:
            self._heading_buf.append(data)

    def close(self):
        super().close()
        self._flush()


def extract(html):
    """(título do primeiro cabeçalho, [parágrafos])."""
    p = _Extractor()
    p.feed(html)
    p.close()
    return p.heading, p.paras


ABBREV = {"sr", "sra", "srta", "dr", "dra", "prof", "profa", "av", "etc", "ex", "pág", "pag", "p", "pp",
          "art", "n", "nº", "vol", "cap", "mr", "mrs", "ms", "st", "jr", "lt", "cel", "gen", "ilmo",
          "exmo", "ltda", "cia", "fig", "obs", "tel", "apt", "ed", "i.e", "e.g", "vs", "no"}
_END = re.compile(r"[.!?…]+[\"”’')»\]]*\s+")
_OPENER = re.compile(r"[A-ZÀ-ÖØ-Þ0-9\"“‘'«(\[—–¿¡-]")
MAX = 150


def _split_long(s):
    out = []
    while len(s) > MAX:
        cut = max(s.rfind(sep, 50, MAX) for sep in (";", ",", ":"))
        if cut < 0:
            cut = s.rfind(" ", 50, MAX)
        if cut < 0:
            cut = MAX
        out.append(s[:cut + 1].strip())
        s = s[cut + 1:].strip()
    if s:
        out.append(s)
    return out


def sentences(paragraph):
    """Divide um parágrafo em frases, sem cortar em abreviações como 'Sr.' ou iniciais."""
    parts, start = [], 0
    for m in _END.finditer(paragraph):
        rest = paragraph[m.end():m.end() + 1]
        before = paragraph[start:m.start()].split()
        last = before[-1].lower().strip("\"“‘'«([—–") if before else ""
        if not rest or not _OPENER.match(rest):
            continue
        if m.group().startswith(".") and (last in ABBREV or (len(last) == 1 and last.isalpha())):
            continue
        parts.append(paragraph[start:m.end()].strip())
        start = m.end()
    parts.append(paragraph[start:].strip())
    out = []
    for p in parts:
        out.extend(_split_long(p))
    return [s for s in out if re.search(r"\w", s)]


def falavel(sentence):
    """Limpa o que o sintetizador lê mal: travessões de diálogo, asteriscos, sublinhados."""
    s = re.sub(r"^\s*[—–-]\s+", "", sentence)
    s = re.sub(r"\s*[—–]\s*", ", ", s)
    s = re.sub(r"[*_#|~^]+", " ", s)
    s = s.replace("…", "...")
    return " ".join(s.split())
