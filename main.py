#!/usr/bin/env python3
"""Splinter, o leitor de livros: lê EPUB em voz alta, só com fala e botões."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# Durante o desenvolvimento, usa a biblioteca do repositório vizinho se não houver cópia aqui.
if not os.path.isdir(os.path.join(HERE, "r36s_a11y")):
    sys.path.insert(1, os.path.join(HERE, "..", "r36s-a11y-sdk", "python"))

import r36s_a11y as a11y
from r36s_a11y import speech as _speech

from leitor.epub import EpubError
from leitor.estado import Estado
from leitor.leitura import Leitura
from leitor.livro import Livro, identificador

PASTAS = [os.environ.get("A11Y_LIVROS"), "/roms/a11y/livros", "/roms/ebooks",
          os.path.expanduser("~/livros"), os.path.join(HERE, "livros")]
PASSO_VELOCIDADE = 10      # unidades do SSIP (-100..100) por aperto
LIMITE_VELOCIDADE = 6      # quantos passos para cada lado
SALVAR_A_CADA = 10.0       # segundos, lendo

game = a11y.Game(repeat=False)
estado = Estado(game.save_dir)
sons = {n: game.sound.load(n, "sounds/%s.wav" % n)
        for n in ("pausa", "retoma", "marca", "borda", "capitulo", "menu_mover", "menu_confirmar")}
menu_sons = {"move": sons["menu_mover"], "select": sons["menu_confirmar"], "edge": sons["borda"]}

# A velocidade é um desvio sobre a voz que o jogador escolheu no sistema.
_voz_original = _speech._user_voice


def _voz_com_velocidade():
    voz = dict(_voz_original())
    desvio = estado.velocidade * PASSO_VELOCIDADE
    if desvio:
        voz["RATE"] = max(-100, min(100, voz.get("RATE", 0) + desvio))
    return voz


_speech._user_voice = _voz_com_velocidade

ctx = {"livros": [], "livro": None, "leitura": None, "tempo": 0.0, "menu": None, "fim": False}


# --- biblioteca ----------------------------------------------------------------
def achar_livros():
    vistos, achados = set(), []
    for pasta in PASTAS:
        if not pasta or not os.path.isdir(pasta):
            continue
        for raiz, dirs, arquivos in os.walk(pasta):
            if raiz[len(pasta):].count(os.sep) >= 2:
                dirs[:] = []
            for nome in sorted(arquivos):
                if nome.lower().endswith(".epub") and not nome.startswith("."):
                    caminho = os.path.join(raiz, nome)
                    ident = identificador(caminho)
                    if ident not in vistos:
                        vistos.add(ident)
                        achados.append((ident, caminho))
    achados.sort(key=lambda a: (-estado.dados["livros"].get(a[0], {}).get("quando", 0),
                                os.path.basename(a[1]).lower()))
    return achados


def nome_na_lista(ident, caminho):
    info = estado.dados["livros"].get(ident, {})
    nome = info.get("titulo") or os.path.splitext(os.path.basename(caminho))[0]
    if info.get("autor"):
        nome += ", de " + info["autor"]
    if info.get("pct") is not None and info.get("pos"):
        nome += ", " + ("terminado" if info.get("terminado") else "%d%% lido" % info["pct"])
    return nome


def abrir_biblioteca():
    fechar_menu()
    ctx["livros"] = achar_livros()
    if not ctx["livros"]:
        game.say("Nenhum livro encontrado. Envie EPUB pela Página no PC, em Livros EPUB, "
                 "ou copie para a pasta a11y, livros, do cartão. Aperte A para sair.")
        return
    itens = [nome_na_lista(i, c) for i, c in ctx["livros"]]
    ctx["menu"] = a11y.Menu(game, "Seus livros", itens, on_select=escolher_livro,
                            on_back=game.quit, sounds=menu_sons)
    ctx["menu"].open()


def fechar_menu():
    m = ctx.get("menu")
    if m is not None and m.is_open:
        m.close()


def escolher_livro(indice, _texto):
    ident, caminho = ctx["livros"][indice]
    fechar_menu()
    game.say("Abrindo o livro. Um momento.")
    try:
        livro = Livro.abrir(caminho)
    except (EpubError, ValueError, OSError) as e:
        game.say("Não consegui abrir este livro. %s" % e)
        game.after(3.0, abrir_biblioteca)
        return
    estado._livro(ident).update(titulo=livro.titulo, autor=livro.autor)
    ctx["livro"] = livro
    pos = estado.posicao(ident)
    if pos is None or not livro.valida(pos):
        pos = (0, 0, 0)
    ctx["fim"] = False
    ctx["leitura"] = Leitura(livro, pos, game.say, game.hush, ao_fim=fim_do_livro)
    abrir_menu_do_livro(primeira=True)


# --- menus do livro --------------------------------------------------------------
def abrir_menu_do_livro(primeira=False):
    fechar_menu()
    livro, leitura = ctx["livro"], ctx["leitura"]
    comeco = leitura.pos == (0, 0, 0)
    itens = ["Começar a ler" if comeco else "Continuar de onde parou", "Capítulos",
             "Marcadores (%d)" % len(estado.marcas(livro.ident)), "Ir para uma porcentagem",
             "Voltar aos livros"]
    titulo = livro.titulo + (", de " + livro.autor if livro.autor and primeira else "")
    if not comeco:
        titulo += ". " + livro.descricao(leitura.pos)
    ctx["menu"] = a11y.Menu(game, titulo, itens, on_select=no_menu_do_livro,
                            on_back=voltar_aos_livros, sounds=menu_sons)
    ctx["menu"].open()


def no_menu_do_livro(indice, _texto):
    if indice == 0:
        if ctx["fim"]:
            ctx["leitura"].ir_para((0, 0, 0), tocar=False)
            ctx["fim"] = False
            estado._livro(ctx["livro"].ident).pop("terminado", None)
        comecar_a_ler()
    elif indice == 1:
        menu_capitulos()
    elif indice == 2:
        menu_marcadores()
    elif indice == 3:
        menu_porcentagem()
    else:
        voltar_aos_livros()


def voltar_aos_livros():
    salvar()
    if ctx["leitura"]:
        ctx["leitura"].pausar()
    game.keep_awake(False)
    ctx.update(livro=None, leitura=None)
    abrir_biblioteca()


def submenu(titulo, itens, ao_escolher, indice=0, classe=a11y.Menu):
    fechar_menu()
    ctx["menu"] = classe(game, titulo, itens, on_select=ao_escolher,
                         on_back=abrir_menu_do_livro, sounds=menu_sons)
    ctx["menu"].open(indice)


def menu_capitulos():
    itens = [c.titulo for c in ctx["livro"].capitulos]
    submenu("Capítulos", itens, lambda i, _t: ler_de((i, 0, 0)), ctx["leitura"].pos[0])


def menu_porcentagem():
    livro = ctx["livro"]
    itens = ["%d por cento" % p for p in range(0, 100, 10)]
    submenu("Ir para", itens, lambda i, _t: ler_de(livro.posicao_de_percentual(i * 10)),
            livro.percentual(ctx["leitura"].pos) // 10)


class MenuMarcadores(a11y.Menu):
    HELP = "Cima e baixo escolhem. B vai até o marcador. X apaga o marcador. A volta."

    def handle_button(self, button, state, ms):
        if button == "x" and state == a11y.DOWN:
            estado.remover_marca(ctx["livro"].ident, self.index)
            self.close()
            game.say("Marcador apagado.")
            game.after(1.2, menu_marcadores)
            return
        super().handle_button(button, state, ms)


def menu_marcadores():
    livro = ctx["livro"]
    marcas = estado.marcas(livro.ident)
    if not marcas:
        fechar_menu()
        game.say("Nenhum marcador neste livro. Durante a leitura, aperte X para marcar o ponto.")
        game.after(4.0, abrir_menu_do_livro)
        return
    itens = ["Marcador %d, %s" % (i + 1, nome) for i, (_, nome) in enumerate(marcas)]
    submenu("Marcadores", itens, lambda i, _t: ler_de(marcas[i][0]), classe=MenuMarcadores)


# --- leitura -------------------------------------------------------------------
def ler_de(pos):
    ctx["fim"] = False
    estado._livro(ctx["livro"].ident).pop("terminado", None)
    ctx["leitura"].ir_para(pos, tocar=False)
    comecar_a_ler()


def comecar_a_ler():
    fechar_menu()
    ctx["tempo"] = 0.0
    sons["retoma"].play()
    ctx["leitura"].tocar()
    game.keep_awake(True)


def salvar():
    livro, leitura = ctx["livro"], ctx["leitura"]
    if livro and leitura:
        info = estado._livro(livro.ident)
        info["pct"] = 100 if info.get("terminado") else livro.percentual(leitura.pos)
        estado.salvar_posicao(livro.ident, leitura.pos)


def fim_do_livro():
    ctx["fim"] = True
    estado._livro(ctx["livro"].ident)["terminado"] = True
    salvar()
    game.keep_awake(False)
    sons["capitulo"].play()
    game.say("Fim do livro. Aperte B para abrir o menu.", queue=True)


def mover(nova, aviso_borda):
    leitura = ctx["leitura"]
    if nova is None:
        sons["borda"].play()
        game.say(aviso_borda)
        return
    ctx["fim"] = False
    estado._livro(ctx["livro"].ident).pop("terminado", None)
    mudou_capitulo = nova[0] != leitura.pos[0]
    leitura.ir_para(nova)
    if not leitura.tocando:
        game.say(leitura.texto_atual())
    if mudou_capitulo:
        sons["capitulo"].play()
    salvar()


def alternar():
    leitura = ctx["leitura"]
    if ctx["fim"]:
        abrir_menu_do_livro()
    elif leitura.tocando:
        leitura.pausar()
        game.keep_awake(False)
        sons["pausa"].play()
        salvar()
    else:
        sons["retoma"].play()
        leitura.tocar()
        game.keep_awake(True)


def marcar():
    livro, leitura = ctx["livro"], ctx["leitura"]
    nome = "%s, %d%% do livro" % (livro.capitulos[leitura.pos[0]].titulo, livro.percentual(leitura.pos))
    n = estado.adicionar_marca(livro.ident, leitura.pos, nome)
    sons["marca"].play()
    game.say("Marcador %d guardado." % n)
    if leitura.tocando:
        leitura.tocar(depois_do_que_esta_falando=True)


def mudar_velocidade(delta):
    leitura = ctx["leitura"]
    novo = max(-LIMITE_VELOCIDADE, min(LIMITE_VELOCIDADE, estado.velocidade + delta))
    if novo == estado.velocidade:
        sons["borda"].play()
        game.say("Já está na %s velocidade." % ("maior" if delta > 0 else "menor"))
        return
    estado.velocidade = novo
    game.say("Velocidade normal." if novo == 0 else
             "Velocidade %s %d." % ("mais" if novo > 0 else "menos", abs(novo)))
    if leitura.tocando:
        leitura.tocar(depois_do_que_esta_falando=True)


def onde_estou():
    livro, leitura = ctx["livro"], ctx["leitura"]
    game.say("%s. %s." % (livro.titulo, livro.descricao(leitura.pos)))
    if leitura.tocando:
        leitura.tocar(depois_do_que_esta_falando=True)


@game.on_start
def inicio():
    game.say("Splinter, leitor de livros.", queue=True)
    abrir_biblioteca()


@game.on_button
def botao(b, st, ms):
    # Com um menu aberto, os botões vão para ele; aqui só chega a leitura em si.
    if st != a11y.DOWN:
        return
    leitura, livro = ctx["leitura"], ctx["livro"]
    if leitura is None:
        if a11y.is_back(b):
            game.quit()
        return
    pos = leitura.pos
    if a11y.is_confirm(b):
        alternar()
    elif b == "right":
        mover(livro.proxima_frase(pos), "Fim do livro.")
    elif b == "left":
        mover(livro.frase_anterior(pos), "Início do livro.")
    elif b == "down":
        mover(livro.proximo_paragrafo(pos), "Fim do livro.")
    elif b == "up":
        mover(livro.paragrafo_anterior(pos), "Início do livro.")
    elif b == "r1":
        mover(livro.proximo_capitulo(pos), "Este é o último capítulo.")
    elif b == "l1":
        mover(livro.capitulo_anterior(pos), "Este é o primeiro capítulo.")
    elif b == "r2":
        mudar_velocidade(1)
    elif b == "l2":
        mudar_velocidade(-1)
    elif b == "x":
        marcar()
    elif b == "y":
        mover(pos, "")
    elif b == "select":
        onde_estou()
    elif b == "start":
        leitura.pausar()
        game.keep_awake(False)
        salvar()
        abrir_menu_do_livro()
    elif a11y.is_back(b):
        voltar_aos_livros()


@game.on_update
def passo(dt):
    leitura = ctx["leitura"]
    if leitura is not None and leitura.tocando:
        ctx["tempo"] += dt
        if ctx["tempo"] >= SALVAR_A_CADA:
            ctx["tempo"] = 0.0
            salvar()


@game.on_quit
def saindo():
    salvar()
    game.keep_awake(False)


game.run()
