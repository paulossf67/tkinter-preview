// Testes do renderer da Webview: alimenta media/preview.js com a saída real
// do parser_tk.py num DOM simulado (jsdom) e verifica o que é desenhado.
// Correr com:  npm test
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { JSDOM } from 'jsdom';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const previewJs = readFileSync(path.join(root, 'media', 'preview.js'), 'utf8');

function parse(source) {
  const res = spawnSync('python', [path.join(root, 'parser_tk.py'), '--stdin', 'teste.py'], {
    input: source,
    encoding: 'utf8',
  });
  assert.equal(res.status, 0, res.stderr);
  return JSON.parse(res.stdout);
}

/** Desenha o código Python e devolve { document, posted }. */
function draw(source) {
  const dom = new JSDOM(
    '<body><div id="toolbar"><span id="status"></span></div><div id="stage"></div></body>',
    { runScripts: 'outside-only' }
  );
  const posted = [];
  dom.window.acquireVsCodeApi = () => ({ postMessage: (m) => posted.push(m) });
  dom.window.eval(previewJs);
  dom.window.dispatchEvent(
    new dom.window.MessageEvent('message', {
      data: { type: 'render', data: parse(source), file: 'teste.py' },
    })
  );
  return { doc: dom.window.document, window: dom.window, posted };
}

const head = 'import tkinter as tk\n';

test('janela com título e tamanho', () => {
  const { doc } = draw(
    head + 'root = tk.Tk()\nroot.title("Minha App")\nroot.geometry("300x200")\n'
  );
  assert.equal(doc.querySelectorAll('.window').length, 1);
  assert.equal(doc.querySelector('.titlebar span').textContent, 'Minha App');
  assert.equal(doc.querySelector('.client').style.width, '300px');
  assert.equal(doc.querySelector('.client').style.height, '200px');
});

test('widgets básicos aparecem com o texto certo', () => {
  const { doc } = draw(
    head +
      'root = tk.Tk()\n' +
      'tk.Label(root, text="Nome:").pack()\n' +
      'tk.Entry(root).pack()\n' +
      'tk.Button(root, text="Salvar").pack()\n'
  );
  assert.equal(doc.querySelector('.w-label').textContent, 'Nome:');
  assert.equal(doc.querySelector('.w-button').textContent, 'Salvar');
  assert.equal(doc.querySelectorAll('.w-entry').length, 1);
});

test('pack side=left agrupa numa linha e bottom vai para o fim', () => {
  const { doc } = draw(
    head +
      'root = tk.Tk()\n' +
      'tk.Label(root, text="topo").pack()\n' +
      'tk.Button(root, text="A").pack(side="left")\n' +
      'tk.Button(root, text="B").pack(side="left")\n' +
      'tk.Label(root, text="rodape").pack(side="bottom")\n'
  );
  const rows = doc.querySelectorAll('.client > .stack > .row');
  assert.equal(rows.length, 1);
  assert.deepEqual(
    [...rows[0].children].map((el) => el.textContent),
    ['A', 'B']
  );
  const stack = doc.querySelector('.client > .stack');
  assert.equal(stack.lastElementChild.textContent, 'rodape');
});

test('grid usa linha e coluna do código', () => {
  const { doc } = draw(
    head +
      'root = tk.Tk()\n' +
      'tk.Label(root, text="X").grid(row=1, column=2, sticky="we")\n'
  );
  const cell = doc.querySelector('.grid > .w-label');
  assert.equal(cell.style.gridRow, '2 / span 1');
  assert.equal(cell.style.gridColumn, '3 / span 1');
  assert.equal(cell.style.justifySelf, 'stretch');
});

test('place posiciona em absoluto', () => {
  const { doc } = draw(
    head + 'root = tk.Tk()\ntk.Button(root, text="Ir").place(x=15, y=40)\n'
  );
  const el = doc.querySelector('.abs > .w-button');
  assert.equal(el.style.left, '15px');
  assert.equal(el.style.top, '40px');
});

test('ciclo for desenha uma instância por iteração, com o texto expandido', () => {
  const { doc } = draw(
    head +
      'root = tk.Tk()\n' +
      'for i, nome in enumerate(["Ana", "Bruno", "Carla"]):\n' +
      '    tk.Label(root, text=nome).grid(row=i, column=0)\n'
  );
  const labels = [...doc.querySelectorAll('.w-label')];
  assert.deepEqual(
    labels.map((el) => el.textContent),
    ['Ana', 'Bruno', 'Carla']
  );
  assert.deepEqual(
    labels.map((el) => el.style.gridRow),
    ['1 / span 1', '2 / span 1', '3 / span 1']
  );
});

test('repetição sem row dinâmico empilha em linhas seguidas', () => {
  const { doc } = draw(
    head +
      'root = tk.Tk()\n' +
      'for i in range(3):\n' +
      '    tk.Label(root, text="fixo").grid(column=0)\n'
  );
  assert.deepEqual(
    [...doc.querySelectorAll('.w-label')].map((el) => el.style.gridRow),
    ['1 / span 1', '2 / span 1', '3 / span 1']
  );
});

test('widgets condicionais são marcados', () => {
  const { doc } = draw(
    head + 'root = tk.Tk()\nif admin:\n    tk.Button(root, text="Apagar").pack()\n'
  );
  assert.ok(doc.querySelector('.w-button').classList.contains('conditional'));
});

test('barra de menus mostra cascatas e entradas', () => {
  const { doc } = draw(
    head +
      'root = tk.Tk()\n' +
      'menubar = tk.Menu(root)\n' +
      'arquivo = tk.Menu(menubar, tearoff=0)\n' +
      'arquivo.add_command(label="Abrir", accelerator="Ctrl+O")\n' +
      'arquivo.add_separator()\n' +
      'arquivo.add_command(label="Sair")\n' +
      'menubar.add_cascade(label="Arquivo", menu=arquivo)\n' +
      'root.config(menu=menubar)\n'
  );
  const items = doc.querySelectorAll('.menubar > .menu-item');
  assert.equal(items.length, 1);
  assert.match(items[0].textContent, /^Arquivo/);
  assert.deepEqual(
    [...items[0].querySelectorAll('.menu-row')].map((el) => el.firstChild.textContent),
    ['Abrir', 'Sair']
  );
  assert.equal(items[0].querySelectorAll('.menu-sep').length, 1);
  // o menu não deve aparecer como widget na área de cliente
  assert.equal(doc.querySelectorAll('.client .w-menu').length, 0);
});

test('itens de Canvas são desenhados em SVG', () => {
  const { doc } = draw(
    head +
      'root = tk.Tk()\n' +
      'c = tk.Canvas(root, width=200, height=100)\n' +
      'c.pack()\n' +
      'c.create_rectangle(10, 10, 60, 40, fill="red")\n' +
      'c.create_oval(70, 10, 110, 50)\n' +
      'c.create_line(0, 90, 200, 90, width=3)\n' +
      'c.create_text(100, 70, text="Oi")\n'
  );
  const svg = doc.querySelector('.w-canvas .canvas-items');
  assert.ok(svg, 'devia existir um SVG dentro do Canvas');
  assert.equal(svg.getAttribute('viewBox'), '0 0 200 100');
  const rect = svg.querySelector('rect');
  assert.equal(rect.getAttribute('fill'), 'red');
  assert.equal(rect.getAttribute('width'), '50');
  assert.ok(svg.querySelector('ellipse'));
  assert.equal(svg.querySelector('polyline').getAttribute('stroke-width'), '3');
  assert.equal(svg.querySelector('text').textContent, 'Oi');
});

test('Notebook desenha as abas pelos nomes dados em add()', () => {
  const { doc } = draw(
    head +
      'from tkinter import ttk\n' +
      'root = tk.Tk()\n' +
      'nb = ttk.Notebook(root)\n' +
      'nb.pack()\n' +
      'geral = ttk.Frame(nb)\n' +
      'nb.add(geral, text="Geral")\n' +
      'avancado = ttk.Frame(nb)\n' +
      'nb.add(avancado, text="Avançado")\n'
  );
  assert.deepEqual(
    [...doc.querySelectorAll('.w-notebook > .tabs > span')].map((el) => el.textContent),
    ['Geral', 'Avançado']
  );
});

test('clicar num widget pede para abrir a linha no editor', () => {
  const { doc, window, posted } = draw(
    head + 'root = tk.Tk()\ntk.Button(root, text="Ok").pack()\n'
  );
  doc.querySelector('.w-button').dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  // os objetos vêm do realm do jsdom, por isso comparamos serializados
  assert.equal(JSON.stringify(posted), JSON.stringify([{ command: 'reveal', line: 3 }]));
});

test('avisos do parser aparecem no painel', () => {
  const { doc } = draw(
    head + 'root = tk.Tk()\nfor x in carregar():\n    tk.Label(root, text="x").pack()\n'
  );
  assert.match(doc.querySelector('.warnings').textContent, /ciclo 'for'/);
});

test('cores e fonte das opções são aplicadas', () => {
  const { doc } = draw(
    head +
      'root = tk.Tk()\n' +
      'tk.Label(root, text="T", bg="#112233", fg="white", font=("Arial", 18, "bold")).pack()\n'
  );
  const el = doc.querySelector('.w-label');
  assert.equal(el.style.color, 'white');
  assert.equal(el.style.fontSize, '18px');
  assert.equal(el.style.fontWeight, 'bold');
  assert.equal(el.style.fontFamily, 'Arial');
});

test('erro de sintaxe é mostrado na barra de estado', () => {
  const dom = new JSDOM(
    '<body><div id="toolbar"><span id="status"></span></div><div id="stage"></div></body>',
    { runScripts: 'outside-only' }
  );
  dom.window.acquireVsCodeApi = () => ({ postMessage: () => {} });
  dom.window.eval(previewJs);
  dom.window.dispatchEvent(
    new dom.window.MessageEvent('message', {
      data: { type: 'render', data: parse('root = tk.Tk(\n') },
    })
  );
  assert.match(dom.window.document.getElementById('status').textContent, /sintaxe/);
  assert.ok(dom.window.document.getElementById('toolbar').classList.contains('error'));
});

test('ficheiro sem Tkinter mostra mensagem de vazio', () => {
  const { doc } = draw('x = 1\nprint(x)\n');
  assert.match(doc.querySelector('.empty').textContent, /Nenhum widget/);
});
