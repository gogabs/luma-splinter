"""Marcadores em formatos abertos: Markdown (para ler) e Web Annotation do W3C (para outros programas).

O Web Annotation (https://www.w3.org/TR/annotation-model/) descreve o destaque pelo texto citado
(TextQuoteSelector: exato, antes e depois), então não depende de onde o trecho cai no arquivo.
"""
import json
import re


def _citacao(texto):
    return "\n".join("> " + p for p in texto.split("\n\n") if p.strip())


def markdown(titulo, autor, marcas):
    linhas = ["# %s" % titulo]
    if autor:
        linhas.append("_%s_" % autor)
    for i, m in enumerate(marcas, 1):
        linhas += ["", "## Marcador %d: %s" % (i, m.get("nome", "")), "", _citacao(m.get("texto", ""))]
    return "\n".join(linhas) + "\n"


def web_annotations(ident, titulo, autor, marcas):
    itens = []
    for i, m in enumerate(marcas, 1):
        itens.append({
            "@context": "http://www.w3.org/ns/anno.jsonld",
            "type": "Annotation",
            "motivation": "highlighting",
            "target": {
                "source": "urn:splinter:%s" % ident,
                "selector": {"type": "TextQuoteSelector", "exact": m.get("texto", ""),
                             "prefix": m.get("antes", ""), "suffix": m.get("depois", "")},
            },
            "dc:title": titulo, "dc:creator": autor, "dc:description": m.get("nome", ""),
        })
    return json.dumps({"@context": "http://www.w3.org/ns/anno.jsonld", "type": "AnnotationCollection",
                       "label": titulo, "total": len(itens), "items": itens}, ensure_ascii=False, indent=2) + "\n"


def nome_de_arquivo(titulo):
    nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", titulo).strip(" .")[:80]
    return nome or "livro"
