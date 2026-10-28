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
from leitor import exportar
from leitor.estado import Estado
from leitor.leitura import Leitura
from leitor.livro import Livro, identificador

PASTAS = [os.environ.get("A11Y_LIVROS"), "/roms/a11y/livros", "/roms/ebooks",
          os.path.expanduser("~/livros"), os.path.join(HERE, "livros")]
PASSO_VELOCIDADE = 10      # unidades do SSIP (-100..100) por aperto
LIMITE_VELOCIDADE = 6      # quantos passos para cada lado
BOTOES_DA_LEITURA = {"left", "right", "up", "down", "l1", "r1", "l2", "r2", "x", "y", "select", "start", "a"}
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

ctx = {"livros": [], "livro": None, "leitura": None, "tempo": 0.0, "menu": None, "fim": False, "sel": None}


def manter_acordado(ligado):
    """Evita a suspensão durante a leitura. Mage Core antigo não tem keep_awake: segue sem."""
    fn = getattr(game, "keep_awake", None)
    if fn is not None:
        fn(ligado)


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
    manter_acordado(False)
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
            exportar_marcas()
            self.close()
            game.say("Marcador apagado.")
            game.after(1.2, menu_marcadores)
            return
        super().handle_button(button, state, ms)


def resumo_da_marca(marca):
    """Texto falado na lista: o começo da citação, com o capítulo."""
    texto = " ".join((marca.get("texto") or "").split())
    if len(texto) > 90:
        texto = texto[:texto.rfind(" ", 40, 90) if texto.rfind(" ", 40, 90) > 0 else 90] + "..."
    return "%s: %s" % (marca.get("nome", ""), texto) if texto else marca.get("nome", "")


def menu_marcadores():
    livro = ctx["livro"]
    marcas = estado.marcas(livro.ident)
    if not marcas:
        fechar_menu()
        game.say("Nenhum marcador neste livro. Durante a leitura, aperte X para marcar o ponto.")
        game.after(4.0, abrir_menu_do_livro)
        return
    itens = ["Marcador %d, %s" % (i + 1, resumo_da_marca(mc)) for i, mc in enumerate(marcas)]
    submenu("Marcadores", itens, lambda i, _t: ler_de(marcas[i]["pos"]), classe=MenuMarcadores)


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
    manter_acordado(True)


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
    manter_acordado(False)
    sons["capitulo"].play()
    game.say("Fim do livro. Aperte B para abrir o menu.", queue=True)


def mover(nova, aviso_borda, ate="frase"):
    """Anda para nova. Lendo sem parar, segue lendo dali; parado (ou em trecho), lê só a frase ou o parágrafo (ate)."""
    leitura = ctx["leitura"]
    if nova is None:
        sons["borda"].play()
        game.say(aviso_borda)
        if leitura.tocando:
            leitura.tocar(depois_do_que_esta_falando=True)
        return
    ctx["fim"] = False
    estado._livro(ctx["livro"].ident).pop("terminado", None)
    mudou_capitulo = nova[0] != leitura.pos[0]
    leitura.ir_para(nova, tocar=True, ate=None if leitura.continua else ate)
    if mudou_capitulo:
        sons["capitulo"].play()
    salvar()


def alternar():
    leitura = ctx["leitura"]
    if ctx["fim"]:
        abrir_menu_do_livro()
    elif leitura.tocando:
        leitura.pausar()
        manter_acordado(False)
        sons["pausa"].play()
        salvar()
    else:
        sons["retoma"].play()
        leitura.tocar()
        manter_acordado(True)


def guardar_marca(ini, fim):
    """Guarda o trecho de ini a fim (inclusive) e atualiza os arquivos de exportação. None se for grande demais."""
    livro = ctx["livro"]
    texto = livro.trecho(ini, fim)
    if texto is None:
        return None
    antes, depois = livro.frase_anterior(ini), livro.proxima_frase(fim)
    nome = "%s, %d%% do livro" % (livro.capitulos[ini[0]].titulo, livro.percentual(ini))
    n = estado.adicionar_marca(livro.ident, ini, nome, fim=fim, texto=texto,
                               antes=livro.frase(antes) if antes else "", depois=livro.frase(depois) if depois else "")
    exportar_marcas()
    return n


def exportar_marcas():
    """Reescreve o Markdown e o JSON (Web Annotation) deste livro em <saves>/exportar."""
    livro = ctx["livro"]
    marcas = estado.marcas(livro.ident)
    pasta = os.path.join(game.save_dir, "exportar")
    base = os.path.join(pasta, exportar.nome_de_arquivo(livro.titulo))
    try:
        os.makedirs(pasta, exist_ok=True)
        if not marcas:
            for ext in (".md", ".json"):
                if os.path.exists(base + ext):
                    os.remove(base + ext)
            return
        with open(base + ".md", "w", encoding="utf-8") as f:
            f.write(exportar.markdown(livro.titulo, livro.autor, marcas))
        with open(base + ".json", "w", encoding="utf-8") as f:
            f.write(exportar.web_annotations(livro.ident, livro.titulo, livro.autor, marcas))
    except OSError:
        pass


def X_apertado():
    """X apertado: pode ser um marcador de uma frase ou o começo de um trecho (segurando e navegando)."""
    leitura = ctx["leitura"]
    retomar = leitura.tocando
    if retomar:
        leitura.pausar()
        manter_acordado(False)
    ctx["sel"] = {"ancora": leitura.pos, "retomar": retomar, "pontas": [(leitura.pos, leitura.pos)], "moveu": False}


def selecao_andou(botao):
    """Chamado depois de uma navegação com X apertado: anota a frase ou o parágrafo onde parou."""
    sel, leitura = ctx["sel"], ctx["leitura"]
    sel["moveu"] = True
    c, p, s = leitura.pos
    # só contam o ponto de partida e onde está agora: voltar encolhe o trecho
    if botao in ("up", "down", "l1", "r1"):
        agora = ((c, p, 0), (c, p, len(ctx["livro"].capitulos[c].paragrafos[p]) - 1))
    else:
        agora = (leitura.pos, leitura.pos)
    sel["pontas"] = [sel["pontas"][0], agora]


def X_solto():
    sel, ctx["sel"] = ctx["sel"], None
    leitura = ctx["leitura"]
    if sel is None:
        return
    ini = min(a for a, _ in sel["pontas"])
    fim = max(b for _, b in sel["pontas"])
    n = guardar_marca(ini, fim)
    if n is None:
        sons["borda"].play()
        game.say("Trecho grande demais para um marcador. Escolha menos.")
    else:
        sons["marca"].play()
        frases = ctx["livro"].contar(ini, fim)
        game.say("Marcador %d guardado%s." % (n, ", trecho de %d frases" % frases if frases > 1 else ""))
    if sel["retomar"]:
        leitura.tocar(depois_do_que_esta_falando=True, ate=None)
        manter_acordado(True)


def mudar_velocidade(delta):
    leitura = ctx["leitura"]
    novo = max(-LIMITE_VELOCIDADE, min(LIMITE_VELOCIDADE, estado.velocidade + delta))
    if novo == estado.velocidade:
        sons["borda"].play()
        game.say("Já está na %s velocidade." % ("maior" if delta > 0 else "menor"))
        if leitura.tocando:
            leitura.tocar(depois_do_que_esta_falando=True)
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
    if b == "x" and st == a11y.UP and ctx["sel"] is not None:
        X_solto()
        return
    if st != a11y.DOWN:
        return
    leitura, livro = ctx["leitura"], ctx["livro"]
    if leitura is None:
        if a11y.is_back(b):
            game.quit()
        return
    print("[splinter] botão %s, lendo=%s" % (b, leitura.tocando), file=sys.stderr)
    if leitura.tocando and b in BOTOES_DA_LEITURA:
        leitura.interromper()            # qualquer entrada corta a frase; cada ação decide como seguir
    pos = leitura.pos
    if a11y.is_confirm(b):
        alternar()
    elif b == "right":
        mover(livro.proxima_frase(pos), "Fim do livro.", "frase")
    elif b == "left":
        mover(livro.frase_anterior(pos), "Início do livro.", "frase")
    elif b == "down":
        mover(livro.proximo_paragrafo(pos), "Fim do livro.", "paragrafo")
    elif b == "up":
        mover(livro.paragrafo_anterior(pos), "Início do livro.", "paragrafo")
    elif b == "r1":
        mover(livro.proximo_capitulo(pos), "Este é o último capítulo.", "paragrafo")
    elif b == "l1":
        mover(livro.capitulo_anterior(pos), "Este é o primeiro capítulo.", "paragrafo")
    elif b == "r2":
        mudar_velocidade(1)
    elif b == "l2":
        mudar_velocidade(-1)
    elif b == "x":
        X_apertado()
    elif b == "y":
        mover(pos, "", "frase")
    elif b == "select":
        onde_estou()
    elif b == "start":
        leitura.pausar()
        manter_acordado(False)
        salvar()
        abrir_menu_do_livro()
    elif a11y.is_back(b):
        voltar_aos_livros()
    if ctx["sel"] is not None and b in ("left", "right", "up", "down", "l1", "r1"):
        selecao_andou(b)


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
    game.hush()          # corta a ajuda do menu ou a leitura, para não vazar para o Luma
    salvar()
    manter_acordado(False)


game.run()
