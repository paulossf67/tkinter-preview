# Tkinter Preview

Extensão do VS Code que mostra, num painel lateral, como fica a janela Tkinter
do ficheiro Python aberto — **sem executar o código**. A análise é estática
(módulo `ast`), por isso é segura mesmo em ficheiros que abririam janelas,
ligariam a bases de dados ou pediriam ficheiros ao arrancar.

## Como correr em modo de desenvolvimento

1. Instale o [Node.js](https://nodejs.org) (LTS). **Ainda não está instalado
   nesta máquina** — sem ele não é possível compilar o TypeScript.
2. Na pasta do projeto:

   ```powershell
   npm install
   npm run compile
   ```

3. Abra a pasta no VS Code e prima `F5` ("Executar Extensão"). Abre-se uma
   segunda janela do VS Code com a extensão carregada.
4. Nessa janela abra [examples/demo.py](examples/demo.py) e clique no botão
   **Abrir Pré-visualização Tkinter** na barra de título do editor (ou use a
   paleta de comandos).

Para trabalhar continuamente use `npm run watch` em vez de `npm run compile`.

## Estrutura

| Ficheiro | Papel |
| --- | --- |
| [parser_tk.py](parser_tk.py) | Percorre a AST do ficheiro e devolve a árvore de widgets em JSON. Recebe o código por `stdin`, para funcionar com o buffer ainda não gravado. |
| [src/extension.ts](src/extension.ts) | Ciclo de vida, painel Webview, deteção do interpretador Python, debounce das alterações. |
| [media/preview.js](media/preview.js) | Desenha o JSON em HTML: janela, gestores de geometria, widgets. |
| [media/preview.css](media/preview.css) | Aspeto clássico do Tkinter no Windows. |

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

Clicar num elemento da pré-visualização salta para a linha que o cria.

## Limites conhecidos

A análise é estática, logo não vê nada que dependa de execução:

- widgets criados dentro de `for`/`if` aparecem uma única vez, sem saber
  quantas iterações haveria;
- valores calculados (`text=f"Total: {n}"`) aparecem como `Total: {...}`;
- opções vindas de variáveis ou dicionários são ignoradas;
- `pack()` é aproximado com flexbox: a ordem e o lado são respeitados, mas a
  repartição exata de espaço do Tk não é reproduzida ao píxel;
- `Canvas` mostra apenas a área em branco, sem os itens desenhados.

## Configurações

| Chave | Omissão | Descrição |
| --- | --- | --- |
| `tkinterPreview.pythonPath` | `""` | Interpretador a usar. Vazio = usa o da extensão `ms-python.python`, senão `python`/`py`/`python3`. |
| `tkinterPreview.liveUpdate` | `true` | Atualizar enquanto digita. `false` = só ao gravar. |
| `tkinterPreview.debounceMs` | `400` | Espera após a última tecla antes de reanalisar. |
