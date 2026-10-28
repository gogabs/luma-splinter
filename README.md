# Splinter, o leitor de livros (R36S / Luma)

Lê EPUB em voz alta, só com fala e botões. Python 3 + Mage Core, sem dependências extras.

**Livros:** pela Página no PC do Luma (cabo USB, `https://r36s.local`), em **Livros EPUB**: escolha um ou vários `.epub` (ou um zip deles) e eles caem em `a11y/livros`. Também dá para copiar os arquivos direto no cartão.

## Botões

Na lista e nos menus: cima/baixo escolhem, B confirma, A volta.

Lendo:

| Botão | Ação |
|---|---|
| B | pausar / continuar |
| esquerda / direita | frase anterior / próxima |
| cima / baixo | parágrafo anterior / próximo (cima no meio do parágrafo volta ao começo dele) |
| L1 / R1 | capítulo anterior / próximo |
| L2 / R2 | fala mais devagar / mais rápida (6 passos, guardado) |
| X | marcador no ponto atual |
| Y | repete a frase |
| Select | diz onde está (capítulo, parágrafo, % do livro) |
| Start | menu do livro: continuar, capítulos, marcadores (X apaga), ir para %, voltar |
| A | volta à lista de livros |

O progresso é salvo ao pausar, navegar, a cada 10 s lendo e ao sair. Ao reabrir o livro, "Continuar de onde parou".

## Desenvolvimento

`python3 -m unittest discover -s tests` (precisa de `../r36s-a11y-sdk` para o teste de fumaça).
`python3 tools/empacotar.py` gera o zip `splinter-<versão>.zip` para `a11y/games`. `python3 tools/gerar_sons.py` regera os bipes. `./instalar.sh [host]` instala no console.

Limites conhecidos: só EPUB sem DRM; texto de imagens não é lido (só o `alt`); a velocidade é um desvio sobre a voz escolhida no sistema.
