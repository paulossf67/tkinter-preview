# Tkinter Preview

Extensão do VS Code que mostra, num painel lateral, como fica a janela Tkinter
do ficheiro Python aberto — **sem executar o código**. A análise é estática
(módulo `ast`), por isso é segura mesmo em ficheiros que abririam janelas,
ligariam a bases de dados ou pediriam ficheiros ao arrancar.

## Como correr em modo de desenvolvimento

```powershell
npm install
npm run compile
```

Depois abra a pasta no VS Code e prima `F5` ("Executar Extensão"). Abre-se uma
segunda janela do VS Code com a extensão carregada; nela abra
[examples/demo.py](examples/demo.py) ou
[examples/avancado.py](examples/avancado.py) e clique em **Abrir
Pré-visualização Tkinter** na barra de título do editor (ou use a paleta de
comandos).

Para trabalhar continuamente use `npm run watch` em vez de `npm run compile`.

### Nota sobre o Node.js nesta máquina

O instalador MSI do Node falha aqui sem elevação (erro 1603), por isso o Node
está como **cópia portátil** em `C:\Users\paulo\.local\node-v24.19.0-win-x64`,
já acrescentada ao `PATH` do utilizador. Se abrir um terminal e o `node` não
for encontrado, feche e reabra o VS Code para o `PATH` ser relido.

## Testes

```powershell
npm test              # renderer: parser real + DOM simulado (jsdom), 16 testes
npm run test:parser   # analisador AST, 23 testes
```

Os testes do renderer correm o `parser_tk.py` a sério e alimentam o
[media/preview.js](media/preview.js) num DOM do `jsdom`, por isso cobrem a
cadeia toda menos a camada do VS Code.

## Estrutura

| Ficheiro | Papel |
| --- | --- |
| [parser_tk.py](parser_tk.py) | Percorre a AST do ficheiro e devolve a árvore de widgets em JSON. Recebe o código por `stdin`, para funcionar com o buffer ainda não gravado. |
| [src/extension.ts](src/extension.ts) | Ciclo de vida, painel Webview, deteção do interpretador Python, debounce das alterações. |
| [media/preview.js](media/preview.js) | Desenha o JSON em HTML: janela, gestores de geometria, widgets, menus e Canvas. |
| [media/preview.css](media/preview.css) | Aspeto clássico do Tkinter no Windows. |
| [tests/](tests/) | Testes do analisador (`unittest`) e do renderer (`node --test` + `jsdom`). |

## O que é reconhecido

- **Janelas**: `Tk()`, `Toplevel()`, classes que herdam de `tk.Tk`/`tk.Frame`
  (o `self` passa a ser o container), `title()`, `geometry()`, `configure()`.
- **Widgets**: Label, Button, Entry, Text, Checkbutton, Radiobutton, Listbox,
  Scale, Scrollbar, Canvas, Combobox, Spinbox, Progressbar, Separator,
  Treeview, Notebook, Frame, LabelFrame — em `tkinter`, `tkinter.ttk` e os
  equivalentes `CTk*` do CustomTkinter.
- **Geometria**: `pack` (side, fill, expand, padx/pady, anchor), `grid` (row,
  column, span, sticky, padx/pady) e `place` (x, y, relx, rely, width, height).
- **Opções visuais**: `text`, `bg`/`fg`, `font`, `width`/`height`, `relief`,
  `state`, `values`, e `insert()` em Entry/Text/Listbox.
- **Formas de escrita**: variável (`btn = tk.Button(...)` + `btn.pack()`),
  atributo (`self.btn = ...`), encadeada (`tk.Label(root, text="x").pack()`) e
  `notebook.add(frame, text="Aba")`.
- **Menus**: `tk.Menu`, `add_command`, `add_cascade`, `add_separator`,
  `accelerator` e `root.config(menu=…)` — desenhados como barra de menus com
  os submenus a abrir ao passar o rato.
- **Canvas**: `create_rectangle`, `create_oval`, `create_line`,
  `create_polygon` e `create_text` são desenhados em SVG à escala do widget.
- **Ciclos `for`**: se o iterável for estático — lista literal, constante do
  módulo, `range(n)` ou `enumerate(...)` — a pré-visualização desenha **uma
  instância por iteração**, e expande expressões que dependam da variável do
  ciclo (`text=f"Linha {i}"`, `row=i`, `text=nome`). Limite de 30 iterações.
- **Ramos condicionais**: widgets dentro de `if`/`else`/`except` aparecem
  tracejados e mais claros, para se ver que podem não existir em execução.
  `if __name__ == "__main__":` não conta como condicional.

Clicar num elemento da pré-visualização salta para a linha que o cria, e os
avisos do analisador aparecem no fim do painel.

## Limites conhecidos

A análise é estática, logo não vê nada que dependa de execução:

- iteráveis que só existem em execução (`for x in carregar():`) desenham uma
  instância e geram um aviso;
- valores calculados fora de um ciclo (`text=f"Total: {n}"`) aparecem como
  `Total: {...}`;
- opções vindas de variáveis, dicionários ou funções são ignoradas;
- `pack()` é aproximado com flexbox: a ordem e o lado são respeitados, mas a
  repartição exata de espaço do Tk não é reproduzida ao píxel;
- no `Canvas`, `create_arc`/`create_image`/`create_window` aparecem como
  retângulos tracejados a marcar a posição;
- estilos de `ttk` (`ttk.Style`, temas) não são interpretados.

## Configurações

| Chave | Omissão | Descrição |
| --- | --- | --- |
| `tkinterPreview.pythonPath` | `""` | Interpretador a usar. Vazio = usa o da extensão `ms-python.python`, senão `python`/`py`/`python3`. |
| `tkinterPreview.liveUpdate` | `true` | Atualizar enquanto digita. `false` = só ao gravar. |
| `tkinterPreview.debounceMs` | `400` | Espera após a última tecla antes de reanalisar. |
