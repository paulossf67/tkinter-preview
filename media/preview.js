// Renderiza na Webview a árvore de widgets devolvida pelo parser_tk.py.
(function () {
  const vscode = acquireVsCodeApi();
  const stage = document.getElementById('stage');
  const status = document.getElementById('status');
  const toolbar = document.getElementById('toolbar');
  let menus = new Map();

  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (msg.type === 'error') {
      toolbar.classList.add('error');
      status.textContent = msg.message;
      return;
    }
    if (msg.type === 'render') {
      toolbar.classList.remove('error');
      render(msg.data);
    }
  });

  function render(data) {
    stage.textContent = '';
    if (!data || data.ok === false) {
      toolbar.classList.add('error');
      status.textContent = data
        ? `${data.error}${data.line ? ' (linha ' + data.line + ')' : ''}`
        : 'Sem dados.';
      return;
    }

    const widgets = data.widgets || [];
    const byId = new Map(widgets.map((w) => [w.id, w]));
    const children = new Map();
    for (const w of widgets) {
      if (!w.parent) continue;
      if (!children.has(w.parent)) children.set(w.parent, []);
      children.get(w.parent).push(w);
    }

    menus = new Map(widgets.filter((w) => w.type === 'Menu').map((w) => [w.id, w]));

    const roots = (data.roots || []).map((id) => byId.get(id)).filter(Boolean);
    if (!roots.length) {
      const hint = document.createElement('div');
      hint.className = 'empty';
      hint.textContent =
        'Nenhum widget Tkinter encontrado neste ficheiro. A pré-visualização procura chamadas como Tk(), Frame(), Label(), Button(), Entry()…';
      stage.appendChild(hint);
      status.textContent = '0 widgets';
      return;
    }

    for (const root of roots) {
      stage.appendChild(renderWindow(root, children));
    }
    const drawn = widgets
      .filter((w) => w.type !== 'Window' && w.type !== 'Menu')
      .reduce((n, w) => n + Math.max(1, Number(w.repeat || 1)), 0);
    const parts = [
      `${drawn} widget(s)`,
      `${roots.length} janela(s)`,
      'clique num elemento para ir ao código',
    ];
    status.textContent = parts.join(' · ');

    const warnings = data.warnings || [];
    if (warnings.length) {
      const box = document.createElement('div');
      box.className = 'warnings';
      for (const text of warnings) {
        const line = document.createElement('div');
        line.textContent = '⚠ ' + text;
        box.appendChild(line);
      }
      stage.appendChild(box);
    }
  }

  // --- janela ---------------------------------------------------------------

  function renderWindow(win, children) {
    const wrap = document.createElement('div');

    const frame = document.createElement('div');
    frame.className = 'window';

    const bar = document.createElement('div');
    bar.className = 'titlebar';
    const title = document.createElement('span');
    title.textContent =
      (win.config && win.config.title) ||
      win.from_class ||
      (win.cls === 'Toplevel' ? 'Toplevel' : 'tk');
    const dots = document.createElement('span');
    dots.className = 'dots';
    dots.innerHTML = '<i></i><i></i><i></i>';
    bar.append(title, dots);

    const client = document.createElement('div');
    client.className = 'client';
    const geom = parseGeometry(win.config && win.config.geometry);
    if (geom) {
      client.style.width = geom.w + 'px';
      client.style.height = geom.h + 'px';
    }
    const bg = color(win.options);
    if (bg) client.style.background = bg;

    layoutChildren(client, children.get(win.id) || [], children);
    frame.append(bar);
    const menubar = renderMenubar(win);
    if (menubar) frame.appendChild(menubar);
    frame.appendChild(client);
    wrap.appendChild(frame);

    if (geom) {
      const hint = document.createElement('div');
      hint.className = 'size-hint';
      hint.textContent = `geometry: ${geom.w}×${geom.h}`;
      wrap.appendChild(hint);
    }
    return wrap;
  }

  // Barra de menus: mostra as cascatas de topo e, ao passar o rato, as entradas.
  function renderMenubar(win) {
    const id = win.config && win.config.menu;
    const menu = id && menus.get(id);
    if (!menu) return null;
    const entries = (menu.config && menu.config.entries) || [];
    if (!entries.length) return null;

    const bar = document.createElement('div');
    bar.className = 'menubar';
    for (const entry of entries) {
      const item = document.createElement('div');
      item.className = 'menu-item';
      const label = document.createElement('span');
      label.textContent = entry.label || '—';
      item.appendChild(label);

      const sub = entry.menu && menus.get(entry.menu);
      if (sub) {
        const drop = document.createElement('div');
        drop.className = 'menu-drop';
        for (const e of (sub.config && sub.config.entries) || []) {
          const row = document.createElement('div');
          if (e.kind === 'separator') {
            row.className = 'menu-sep';
          } else {
            row.className = 'menu-row';
            row.textContent = e.label || '';
            if (e.kind === 'checkbutton' || e.kind === 'radiobutton') {
              row.textContent = '□ ' + row.textContent;
            }
            if (e.accelerator) {
              const acc = document.createElement('span');
              acc.className = 'menu-acc';
              acc.textContent = e.accelerator;
              row.appendChild(acc);
            }
          }
          drop.appendChild(row);
        }
        item.appendChild(drop);
        item.addEventListener('click', () => {
          vscode.postMessage({ command: 'reveal', line: sub.line });
        });
      }
      bar.appendChild(item);
    }
    return bar;
  }

  function parseGeometry(value) {
    if (typeof value !== 'string') return null;
    const m = /^(\d+)x(\d+)/.exec(value);
    return m ? { w: +m[1], h: +m[2] } : null;
  }

  // --- distribuição por gestor de geometria --------------------------------

  function layoutChildren(container, kids, children) {
    if (!kids.length) return;

    const manager = dominantManager(kids);
    if (manager === 'place') {
      container.classList.add('abs');
      for (const k of kids) {
        const el = renderWidget(k, children);
        applyPlace(el, k.layout || {});
        container.appendChild(el);
      }
      return;
    }

    if (manager === 'grid') {
      const grid = document.createElement('div');
      grid.className = 'grid';
      for (const k of kids) {
        const el = renderWidget(k, children);
        applyGrid(el, k.layout || {});
        grid.appendChild(el);
      }
      container.appendChild(grid);
      return;
    }

    container.appendChild(packStack(kids, children));
  }

  function dominantManager(kids) {
    const count = { pack: 0, grid: 0, place: 0 };
    for (const k of kids) {
      const m = k.layout && k.layout.manager;
      if (m === 'grid' || m === 'place' || m === 'pack') count[m]++;
    }
    if (count.place >= count.grid && count.place > count.pack) return 'place';
    if (count.grid > count.pack) return 'grid';
    return 'pack';
  }

  // pack(): empilha top/bottom, agrupa left/right consecutivos numa linha.
  function packStack(kids, children) {
    const stack = document.createElement('div');
    stack.className = 'stack';
    const bottom = [];
    let row = null;

    for (const k of kids) {
      const layout = k.layout || {};
      const side = String(layout.side || 'top').toLowerCase();
      const el = renderWidget(k, children);
      applyPack(el, layout, side);

      if (side === 'left' || side === 'right') {
        if (!row) {
          row = document.createElement('div');
          row.className = 'row';
          stack.appendChild(row);
        }
        if (side === 'right') row.prepend(el);
        else row.appendChild(el);
        continue;
      }
      row = null;
      if (side === 'bottom') bottom.unshift(el);
      else stack.appendChild(el);
    }
    for (const el of bottom) stack.appendChild(el);
    return stack;
  }

  function applyPack(el, layout, side) {
    const fill = String(layout.fill || 'none').toLowerCase();
    const horizontal = side === 'left' || side === 'right';
    if (fill === 'both') {
      el.style.alignSelf = 'stretch';
      el.style.flex = '1 1 auto';
    } else if (fill === 'x') {
      if (horizontal) el.style.flex = '1 1 auto';
      else el.style.alignSelf = 'stretch';
    } else if (fill === 'y') {
      if (horizontal) el.style.alignSelf = 'stretch';
      else el.style.flex = '1 1 auto';
    } else {
      const anchor = String(layout.anchor || '').toLowerCase();
      if (!horizontal) {
        el.style.alignSelf = anchor.includes('w')
          ? 'flex-start'
          : anchor.includes('e')
          ? 'flex-end'
          : 'center';
      }
    }
    if (layout.expand) el.style.flexGrow = '1';
    applyPadding(el, layout);
  }

  function applyGrid(el, layout) {
    const row = Number(layout.row || 0);
    const col = Number(layout.column || 0);
    el.style.gridRow = `${row + 1} / span ${Number(layout.rowspan || 1)}`;
    el.style.gridColumn = `${col + 1} / span ${Number(layout.columnspan || 1)}`;
    const sticky = String(layout.sticky || '').toLowerCase();
    if (sticky.includes('w') && sticky.includes('e')) el.style.justifySelf = 'stretch';
    else if (sticky.includes('w')) el.style.justifySelf = 'start';
    else if (sticky.includes('e')) el.style.justifySelf = 'end';
    if (sticky.includes('n') && sticky.includes('s')) el.style.alignSelf = 'stretch';
    else if (sticky.includes('n')) el.style.alignSelf = 'start';
    else if (sticky.includes('s')) el.style.alignSelf = 'end';
    applyPadding(el, layout);
  }

  function applyPlace(el, layout) {
    if (layout.x !== undefined) el.style.left = Number(layout.x) + 'px';
    if (layout.y !== undefined) el.style.top = Number(layout.y) + 'px';
    if (layout.relx !== undefined) el.style.left = Number(layout.relx) * 100 + '%';
    if (layout.rely !== undefined) el.style.top = Number(layout.rely) * 100 + '%';
    if (layout.width !== undefined) el.style.width = Number(layout.width) + 'px';
    if (layout.height !== undefined) el.style.height = Number(layout.height) + 'px';
    if (layout.relwidth !== undefined) el.style.width = Number(layout.relwidth) * 100 + '%';
    if (layout.relheight !== undefined) el.style.height = Number(layout.relheight) * 100 + '%';
    const anchor = String(layout.anchor || 'nw').toLowerCase();
    if (anchor === 'center') el.style.transform = 'translate(-50%, -50%)';
  }

  function applyPadding(el, layout) {
    const pad = (v) => (Array.isArray(v) ? v.map(Number) : [Number(v), Number(v)]);
    if (layout.padx !== undefined) {
      const [l, r] = pad(layout.padx);
      el.style.marginLeft = (l || 0) + 'px';
      el.style.marginRight = (r || l || 0) + 'px';
    }
    if (layout.pady !== undefined) {
      const [t, b] = pad(layout.pady);
      el.style.marginTop = (t || 0) + 'px';
      el.style.marginBottom = (b || t || 0) + 'px';
    }
  }

  // --- widgets --------------------------------------------------------------

  function renderWidget(w, children) {
    const opts = w.options || {};
    const el = document.createElement('div');
    el.className = 'widget w-' + w.type.toLowerCase();
    el.title = `${w.cls} (linha ${w.line}) — clique para abrir no editor`;
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      vscode.postMessage({ command: 'reveal', line: w.line });
    });

    const text = opts.text !== undefined ? String(opts.text) : '';
    const items = (w.config && w.config.items) || [];

    switch (w.type) {
      case 'Label':
        el.textContent = text || 'Label';
        break;
      case 'Button':
        el.textContent = text || 'Button';
        break;
      case 'Entry':
        el.textContent = items[0] || opts.placeholder_text || '';
        break;
      case 'Spinbox':
        el.textContent = (items[0] || '0') + '  ⬍';
        break;
      case 'Combobox': {
        const values = Array.isArray(opts.values) ? opts.values : [];
        el.textContent = values[0] !== undefined ? String(values[0]) : text;
        break;
      }
      case 'Text':
        el.textContent = items.join('') || '';
        break;
      case 'Listbox':
        el.textContent = items.join('\n');
        break;
      case 'Checkbutton':
      case 'Radiobutton': {
        const box = document.createElement('span');
        box.className = 'box';
        const label = document.createElement('span');
        label.textContent = text || w.type;
        el.append(box, label);
        break;
      }
      case 'Scale': {
        const track = document.createElement('div');
        track.className = 'track';
        const knob = document.createElement('div');
        knob.className = 'knob';
        track.appendChild(knob);
        el.appendChild(track);
        break;
      }
      case 'Scrollbar':
        if (String(opts.orient || 'vertical').toLowerCase() === 'horizontal') {
          el.classList.add('horizontal');
        }
        break;
      case 'Progressbar': {
        const bar = document.createElement('span');
        el.appendChild(bar);
        break;
      }
      case 'Separator':
        break;
      case 'Treeview': {
        const head = document.createElement('div');
        head.className = 'head';
        head.textContent = (Array.isArray(opts.values) ? opts.values : ['#0']).join('   ');
        el.appendChild(head);
        break;
      }
      case 'Canvas':
        break;
      case 'Notebook': {
        const tabs = document.createElement('div');
        tabs.className = 'tabs';
        const pages = document.createElement('div');
        pages.className = 'pages';
        const kids = children.get(w.id) || [];
        kids.forEach((k, i) => {
          const tab = document.createElement('span');
          tab.textContent = (k.layout && k.layout.text) || k.id;
          if (i === 0) tab.classList.add('active');
          tabs.appendChild(tab);
        });
        if (kids.length) {
          const first = renderWidget(kids[0], children);
          pages.appendChild(first);
        }
        el.append(tabs, pages);
        return sized(el, opts);
      }
      case 'LabelFrame': {
        const cap = document.createElement('span');
        cap.className = 'lf-title';
        cap.textContent = text || '';
        el.appendChild(cap);
        layoutChildren(el, children.get(w.id) || [], children);
        return sized(el, opts);
      }
      case 'Frame':
      case 'Window':
        layoutChildren(el, children.get(w.id) || [], children);
        return sized(el, opts);
      default:
        el.classList.add('unknown');
        el.textContent = w.cls;
    }

    if (w.container && w.type !== 'Notebook') {
      layoutChildren(el, children.get(w.id) || [], children);
    }
    return sized(el, opts);
  }

  // width/height em Tkinter são caracteres (texto) ou píxeis (Frame/Canvas).
  function sized(el, opts) {
    const bg = color(opts);
    if (bg) el.style.background = bg;
    const fg = opts.fg || opts.foreground || opts.text_color;
    if (typeof fg === 'string') el.style.color = fg;
    if (typeof opts.font === 'string' || Array.isArray(opts.font)) {
      applyFont(el, opts.font);
    }
    const pixelSized = ['w-frame', 'w-canvas', 'w-labelframe'].some((c) =>
      el.classList.contains(c)
    );
    if (typeof opts.width === 'number') {
      el.style.width = (pixelSized ? opts.width : opts.width * 8) + 'px';
    }
    if (typeof opts.height === 'number') {
      el.style.height = (pixelSized ? opts.height : opts.height * 18) + 'px';
    }
    const relief = String(opts.relief || '').toLowerCase();
    if (relief === 'sunken' || relief === 'groove') el.style.border = '1px inset #9a9a9a';
    else if (relief === 'raised' || relief === 'ridge') el.style.border = '1px outset #d4d4d4';
    else if (relief === 'solid') el.style.border = '1px solid #9a9a9a';
    if (String(opts.state || '').toLowerCase() === 'disabled') el.style.opacity = '0.55';
    return el;
  }

  function applyFont(el, font) {
    const parts = Array.isArray(font) ? font : String(font).split(/\s+/);
    const family = parts[0];
    const size = Number(parts[1]);
    const style = parts.slice(2).join(' ').toLowerCase();
    if (family && isNaN(Number(family))) el.style.fontFamily = String(family);
    if (!isNaN(size) && size) el.style.fontSize = Math.abs(size) + 'px';
    if (style.includes('bold')) el.style.fontWeight = 'bold';
    if (style.includes('italic')) el.style.fontStyle = 'italic';
    if (style.includes('underline')) el.style.textDecoration = 'underline';
  }

  function color(opts) {
    const v = opts && (opts.bg || opts.background || opts.fg_color);
    return typeof v === 'string' ? v : null;
  }
})();
