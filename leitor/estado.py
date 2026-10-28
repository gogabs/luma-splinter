"""Progresso, marcadores e velocidade, num JSON na pasta de saves."""
import json
import os
import time


class Estado:
    def __init__(self, pasta):
        self.arquivo = os.path.join(pasta, "progresso.json")
        self.dados = {"livros": {}, "velocidade": 0}
        try:
            with open(self.arquivo, encoding="utf-8") as f:
                lido = json.load(f)
            if isinstance(lido, dict):
                self.dados.update(lido)
        except (OSError, ValueError):
            pass

    def _livro(self, ident):
        return self.dados["livros"].setdefault(ident, {"pos": None, "marcas": []})

    def posicao(self, ident):
        pos = self.dados["livros"].get(ident, {}).get("pos")
        return tuple(pos) if pos else None

    def salvar_posicao(self, ident, pos):
        self._livro(ident)["pos"] = list(pos)
        self._livro(ident)["quando"] = int(time.time())
        self.gravar()

    def marcas(self, ident):
        return [(tuple(m["pos"]), m.get("nome", "")) for m in self._livro(ident)["marcas"]]

    def adicionar_marca(self, ident, pos, nome):
        self._livro(ident)["marcas"].append({"pos": list(pos), "nome": nome})
        self.gravar()
        return len(self._livro(ident)["marcas"])

    def remover_marca(self, ident, indice):
        marcas = self._livro(ident)["marcas"]
        if 0 <= indice < len(marcas):
            del marcas[indice]
            self.gravar()

    @property
    def velocidade(self):
        return int(self.dados.get("velocidade", 0))

    @velocidade.setter
    def velocidade(self, v):
        self.dados["velocidade"] = int(v)
        self.gravar()

    def gravar(self):
        try:
            os.makedirs(os.path.dirname(self.arquivo), exist_ok=True)
            tmp = self.arquivo + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.dados, f, ensure_ascii=False)
            os.replace(tmp, self.arquivo)
        except OSError:
            pass
