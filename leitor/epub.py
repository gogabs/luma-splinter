"""Abre um EPUB só com a biblioteca padrão: metadados, ordem de leitura e sumário."""
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from urllib.parse import unquote


class EpubError(Exception):
    pass


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _text(node):
    return " ".join("".join(node.itertext()).split())


def _decode(data):
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeError:
            pass
    return data.decode("latin-1")


class Epub:
    """title, author, spine (lista de caminhos no zip) e toc ({caminho: título})."""

    def __init__(self, path):
        try:
            self.zip = zipfile.ZipFile(path)
            self._names = {n.lower(): n for n in self.zip.namelist()}
            self.opf_path = self._find_opf()
            root = ET.fromstring(self.zip.read(self.opf_path))
        except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError) as e:
            raise EpubError("Não consegui abrir o arquivo: %s" % e)
        self.base = posixpath.dirname(self.opf_path)
        self.title = self.author = ""
        manifest, spine, toc_id = {}, [], None
        for el in root.iter():
            name = _local(el.tag)
            if name == "title" and not self.title:
                self.title = _text(el)
            elif name == "creator" and not self.author:
                self.author = _text(el)
            elif name == "item":
                manifest[el.get("id")] = el
            elif name == "spine":
                toc_id = el.get("toc")
            elif name == "itemref":
                spine.append(el)
        self.spine = []
        for ref in spine:
            item = manifest.get(ref.get("idref"))
            if item is None:
                continue
            kind = item.get("media-type", "")
            if "html" in kind or "xml" in kind and "ncx" not in kind and "dtbook" not in kind:
                self.spine.append(self._join(item.get("href", "")))
        self.toc = {}
        nav = next((m for m in manifest.values() if "nav" in (m.get("properties") or "").split()), None)
        ncx = manifest.get(toc_id) if toc_id else None
        if ncx is None:
            ncx = next((m for m in manifest.values() if m.get("media-type") == "application/x-dtbncx+xml"), None)
        try:
            if nav is not None:
                self._read_nav(self._join(nav.get("href", "")))
            if not self.toc and ncx is not None:
                self._read_ncx(self._join(ncx.get("href", "")))
        except (KeyError, ET.ParseError):
            pass

    def _find_opf(self):
        container = ET.fromstring(self.zip.read(self._names["meta-inf/container.xml"]))
        for el in container.iter():
            if _local(el.tag) == "rootfile" and el.get("full-path"):
                return self._real(unquote(el.get("full-path")))
        raise KeyError("sem rootfile")

    def _real(self, name):
        return self._names.get(name.lower(), name)

    def _join(self, href):
        href = unquote(href.split("#", 1)[0])
        return self._real(posixpath.normpath(posixpath.join(self.base, href)))

    def read(self, name):
        return _decode(self.zip.read(name))

    def _add_toc(self, href, title):
        key = self._join(href)
        title = " ".join(title.split())
        if title and key not in self.toc:
            self.toc[key] = title

    def _read_ncx(self, name):
        root = ET.fromstring(self.zip.read(name))
        for point in root.iter():
            if _local(point.tag) != "navPoint":
                continue
            label = src = None
            for child in point:
                if _local(child.tag) == "navLabel" and label is None:
                    label = _text(child)
                elif _local(child.tag) == "content" and src is None:
                    src = child.get("src")
            if label and src:
                self._add_toc(src, label)

    def _read_nav(self, name):
        parser = _NavParser()
        parser.feed(self.read(name))
        for href, title in parser.links:
            self._add_toc(href, title)


class _NavParser(HTMLParser):
    """Links do primeiro <nav> de sumário (ou do primeiro nav, se nenhum se declarar)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.navs = []      # (é_toc, [(href, texto)])
        self._in_nav = 0
        self._href = None
        self._buf = []

    @property
    def links(self):
        toc = [n for n in self.navs if n[0]]
        return (toc or self.navs or [(0, [])])[0][1]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "nav":
            self.navs.append((("toc" in (a.get("epub:type") or a.get("type") or "")), []))
            self._in_nav += 1
        elif tag == "a" and self._in_nav and a.get("href"):
            self._href, self._buf = a["href"], []

    def handle_data(self, data):
        if self._href is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.navs[-1][1].append((self._href, "".join(self._buf)))
            self._href = None
        elif tag == "nav" and self._in_nav:
            self._in_nav -= 1
