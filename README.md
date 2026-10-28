# Splinter, o leitor de livros (R36S / Luma)

Lê EPUB em voz alta, só com fala e botões. Python 3 + Mage Core, sem dependências extras.

**Livros:** pela Página no PC do Luma (cabo USB, `https://r36s.local`), em **Livros EPUB**: escolha um ou vários `.epub` (ou um zip deles) e eles caem em `a11y/livros`. Também dá para copiar os arquivos direto no cartão.

## Botões

Na lista e nos menus: cima/baixo escolhem, B confirma, A volta.

Lendo:

| Botão | Ação |
|---|---|
| B | pausar / continuar |
| esquerda / direita | frase anterior / próxima (parado, lê só essa frase) |
| cima / baixo | parágrafo anterior / próximo (cima no meio do parágrafo volta ao começo dele). Parado, lê o parágrafo inteiro, frase por frase, e para |
| L1 / R1 | capítulo anterior / próximo |
| L2 / R2 | fala mais devagar / mais rápida (6 passos, guardado) |
| X | marca a frase atual. Segurando X e navegando (esquerda/direita, cima/baixo), marca um trecho: a primeira frase é o início e a última o fim |
| Y | repete a frase |
| Select | diz onde está (capítulo, parágrafo, % do livro) |
| Start | menu do livro: continuar, capítulos, marcadores (X apaga), ir para %, voltar |
| A | volta à lista de livros |

O progresso é salvo ao pausar, navegar, a cada 10 s lendo e ao sair. Ao reabrir o livro, "Continuar de onde parou".

## Desenvolvimento

`python3 -m unittest discover -s tests` (precisa de `../r36s-a11y-sdk` para o teste de fumaça).
`python3 tools/empacotar.py` gera o zip `splinter-<versão>.zip` para `a11y/games`. `python3 tools/gerar_sons.py` regera os bipes. `./instalar.sh [host]` instala no console.

Limites conhecidos: só EPUB sem DRM; texto de imagens não é lido (só o `alt`); a velocidade é um desvio sobre a voz escolhida no sistema.

## Marcadores e exportação

A lista de marcadores (Start, Marcadores) fala o capítulo e o começo do texto marcado. A cada mudança, o Splinter
grava em `a11y/saves/splinter/exportar/` dois arquivos por livro: `<título>.md` (Markdown, para ler) e `<título>.json`
([Web Annotation do W3C](https://www.w3.org/TR/annotation-model/), com o trecho exato e o contexto antes e depois,
que não depende da posição no arquivo). A página do Luma no PC vai oferecer esses arquivos para baixar.
