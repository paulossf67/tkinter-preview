"""Analisador estático de interfaces Tkinter.

Lê um ficheiro .py, percorre a AST e devolve em JSON a árvore de widgets
(tipo, pai, opções e gestor de geometria) para ser desenhada na Webview
do VS Code. Nada do código do utilizador é executado.

Uso:  python parser_tk.py <ficheiro.py>
      python parser_tk.py --stdin      (código lido do stdin)
"""

import ast
import json
import sys

# Widgets que sabemos desenhar. O valor é o nome normalizado usado no renderer.
WIDGETS = {
    "Tk": "Window",
    "Toplevel": "Window",
    "CTk": "Window",
    "CTkToplevel": "Window",
    "Frame": "Frame",
    "CTkFrame": "Frame",
    "LabelFrame": "LabelFrame",
    "Labelframe": "LabelFrame",
    "Label": "Label",
    "CTkLabel": "Label",
    "Button": "Button",
    "CTkButton": "Button",
    "Entry": "Entry",
    "CTkEntry": "Entry",
    "Text": "Text",
    "CTkTextbox": "Text",
    "Checkbutton": "Checkbutton",
    "CTkCheckBox": "Checkbutton",
    "Radiobutton": "Radiobutton",
    "CTkRadioButton": "Radiobutton",
    "Listbox": "Listbox",
    "Scale": "Scale",
    "CTkSlider": "Scale",
    "Scrollbar": "Scrollbar",
    "Canvas": "Canvas",
    "Combobox": "Combobox",
    "CTkComboBox": "Combobox",
    "CTkOptionMenu": "Combobox",
    "OptionMenu": "Combobox",
    "Spinbox": "Spinbox",
    "Progressbar": "Progressbar",
    "CTkProgressBar": "Progressbar",
    "Separator": "Separator",
    "Treeview": "Treeview",
    "Notebook": "Notebook",
    "PanedWindow": "Frame",
    "Panedwindow": "Frame",
    "Message": "Label",
    "Menubutton": "Button",
    "CTkSwitch": "Checkbutton",
    "CTkScrollableFrame": "Frame",
    "Menu": "Menu",
}

# Itens desenhados num Canvas: create_rectangle, create_text, ...
CANVAS_ITEMS = {
    "create_rectangle", "create_oval", "create_line", "create_text",
    "create_arc", "create_polygon", "create_image", "create_window",
}

# Métodos que acrescentam entradas a um Menu.
MENU_ADDERS = {
    "add_command": "command",
    "add_cascade": "cascade",
    "add_separator": "separator",
    "add_checkbutton": "checkbutton",
    "add_radiobutton": "radiobutton",
}

# Widgets que podem conter outros widgets.
CONTAINERS = {"Window", "Frame", "LabelFrame", "Canvas", "Notebook"}

# Opções cujo valor nos interessa (constantes literais apenas).
OPTION_KEYS = {
    "text", "bg", "background", "fg", "foreground", "width", "height",
    "font", "relief", "borderwidth", "bd", "anchor", "justify", "state",
    "wraplength", "padx", "pady", "values", "from_", "to", "value",
    "orient", "show", "selectmode", "cursor", "activebackground",
    "highlightthickness", "textvariable", "variable", "image",
    "text_color", "fg_color", "corner_radius", "placeholder_text",
}

LAYOUT_KEYS = {
    "pack": {"side", "fill", "expand", "padx", "pady", "anchor", "ipadx", "ipady", "before", "after"},
    "grid": {"row", "column", "columnspan", "rowspan", "sticky", "padx", "pady", "ipadx", "ipady"},
    "place": {"x", "y", "relx", "rely", "width", "height", "relwidth", "relheight", "anchor"},
}


def plain(value):
    """Normaliza tuplos/conjuntos em listas, para o JSON sair estável."""
    if isinstance(value, tuple):
        return [plain(v) for v in value]
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def literal(node):
    """Devolve o valor literal de um nó, ou None se não for estático."""
    try:
        return plain(ast.literal_eval(node))
    except Exception:
        pass
    if isinstance(node, ast.Attribute):
        # tk.LEFT, tk.BOTH, tkinter.W ... -> "left", "both", "w"
        known = {
            "LEFT": "left", "RIGHT": "right", "TOP": "top", "BOTTOM": "bottom",
            "BOTH": "both", "X": "x", "Y": "y", "NONE": "none",
            "N": "n", "S": "s", "E": "e", "W": "w", "NE": "ne", "NW": "nw",
            "SE": "se", "SW": "sw", "CENTER": "center", "NSEW": "nsew",
            "HORIZONTAL": "horizontal", "VERTICAL": "vertical",
            "FLAT": "flat", "RAISED": "raised", "SUNKEN": "sunken",
            "GROOVE": "groove", "RIDGE": "ridge", "SOLID": "solid",
            "DISABLED": "disabled", "NORMAL": "normal",
            "TRUE": True, "FALSE": False, "YES": True, "NO": False,
        }
        if node.attr in known:
            return known[node.attr]
    if isinstance(node, ast.JoinedStr):
        # f-string: mostra as partes constantes e marca o resto
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(str(v.value))
            else:
                out.append("{...}")
        return "".join(out)
    return None


def dotted_name(node):
    """'x' para Name, 'self.btn' para Attribute simples, senão None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        if base is not None:
            return base + "." + node.attr
    return None


def is_main_guard(test):
    """Reconhece `__name__ == "__main__"`."""
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
    )


MAX_REPEAT = 30


def loop_values(node):
    """Valores percorridos por um `for`, se forem estáticos.

    Suporta listas/tuplos literais, `range(...)` com constantes e
    `enumerate(lista_literal)`.
    """
    direct = literal(node)
    if isinstance(direct, (list, tuple)):
        return list(direct)[:MAX_REPEAT]

    if isinstance(node, ast.Call):
        fn = node.func.id if isinstance(node.func, ast.Name) else None
        args = [literal(a) for a in node.args]
        if fn == "range" and args and all(isinstance(a, int) for a in args):
            try:
                return list(range(*args))[:MAX_REPEAT]
            except (TypeError, ValueError):
                return None
        if fn == "enumerate" and node.args:
            inner = loop_values(node.args[0])
            if inner:
                return [(i, v) for i, v in enumerate(inner)]
    return None


def target_names(node):
    """Nomes ligados pelo `for`: 'i' ou ['i', 'nome'] num desempacotamento."""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names = []
        for el in node.elts:
            if not isinstance(el, ast.Name):
                return None
            names.append(el.id)
        return names
    return None


def loop_env(loop, value):
    """Associa os nomes do `for` a um dos valores percorridos."""
    names = loop["vars"]
    if len(names) == 1:
        return {names[0]: value}
    if isinstance(value, (list, tuple)) and len(value) == len(names):
        return dict(zip(names, value))
    return None


def expand_over_loop(node, loop):
    """Avalia `node` uma vez por iteração, se depender só das variáveis do ciclo.

    Devolve a lista de valores, ou None se não for possível.
    """
    used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
    if not used or used - set(loop["vars"]):
        return None
    out = []
    for value in loop["values"]:
        env = loop_env(loop, value)
        if env is None:
            return None
        try:
            out.append(subst(node, env))
        except Exception:
            return None
    return out


def subst(node, env):
    """Avalia uma expressão simples com as variáveis do ciclo em `env`."""
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise ValueError(node.id)
        return env[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(str(v.value))
            elif isinstance(v, ast.FormattedValue):
                parts.append(str(subst(v.value, env)))
            else:
                raise ValueError("joinedstr")
        return "".join(parts)
    if isinstance(node, ast.BinOp):
        left = subst(node.left, env)
        right = subst(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Sub):
            return left - right
        raise ValueError("binop")
    if isinstance(node, ast.Subscript):
        # i[0] / i[1] de um enumerate
        base = subst(node.value, env)
        idx = literal(node.slice)
        if isinstance(base, (list, tuple)) and isinstance(idx, int):
            return base[idx]
        raise ValueError("subscript")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str":
        return str(subst(node.args[0], env))
    raise ValueError(type(node).__name__)


def call_class(node):
    """Nome da classe chamada: Button(...) ou tk.Button(...) -> 'Button'."""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
    return None


class TkinterParser(ast.NodeVisitor):
    def __init__(self):
        self.widgets = []          # ordem de criação
        self.by_id = {}            # nome da variável -> widget
        self.warnings = []
        self.anon = 0
        self.class_stack = []      # tipo de container associado a 'self'
        self.loop_stack = []       # ciclos 'for' em curso: {"var", "values"}
        self.cond_depth = 0        # dentro de quantos 'if'/'try' estamos

    # -- criação -----------------------------------------------------------

    def new_widget(self, cls, node, var=None):
        kind = WIDGETS[cls]
        if var is None:
            self.anon += 1
            var = "__anon%d" % self.anon
        parent = None
        if node.args:
            parent = dotted_name(node.args[0])
        if parent is None:
            for kw in node.keywords:
                if kw.arg in ("master", "parent"):
                    parent = dotted_name(kw.value)
        loop = self.loop_stack[-1] if self.loop_stack else None
        options = {}
        per_instance = {}
        for kw in node.keywords:
            if kw.arg not in OPTION_KEYS:
                continue
            val = None
            if loop is not None:
                seq = expand_over_loop(kw.value, loop)
                if seq is not None:
                    per_instance[kw.arg] = seq
                    val = seq[0]
            if val is None:
                val = literal(kw.value)
            if val is not None:
                options[kw.arg] = val
        w = {
            "id": var,
            "cls": cls,
            "type": kind,
            "parent": parent,
            "options": options,
            "layout": None,
            "config": {},
            "line": node.lineno,
            "container": kind in CONTAINERS,
        }
        if loop is not None:
            w["repeat"] = len(loop["values"])
            if per_instance:
                w["per_instance"] = per_instance
        if self.cond_depth:
            w["conditional"] = True
        self.widgets.append(w)
        self.by_id[var] = w
        return w

    # -- visitas -----------------------------------------------------------

    def visit_For(self, node):
        names = target_names(node.target)
        values = loop_values(node.iter)
        if names and values:
            self.loop_stack.append({"vars": names, "values": values})
            for stmt in node.body:
                self.visit(stmt)
            self.loop_stack.pop()
            for stmt in node.orelse:
                self.visit(stmt)
            return
        # Ciclo que não conseguimos contar: desenha uma instância só.
        self.warnings.append(
            "Linha %d: ciclo 'for' com iterável não literal — só uma instância é mostrada."
            % node.lineno
        )
        self.generic_visit(node)

    def visit_While(self, node):
        self.warnings.append(
            "Linha %d: widgets dentro de 'while' aparecem uma única vez." % node.lineno
        )
        self.cond_depth += 1
        self.generic_visit(node)
        self.cond_depth -= 1

    def visit_If(self, node):
        # `if __name__ == "__main__":` corre sempre na prática.
        main_guard = is_main_guard(node.test)
        if not main_guard:
            self.cond_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        if not main_guard:
            self.cond_depth -= 1
        self.cond_depth += 1
        for stmt in node.orelse:
            self.visit(stmt)
        self.cond_depth -= 1

    def visit_Try(self, node):
        for stmt in node.body:
            self.visit(stmt)
        self.cond_depth += 1
        for group in (node.handlers, node.orelse, node.finalbody):
            for stmt in group:
                self.visit(stmt)
        self.cond_depth -= 1

    def visit_ClassDef(self, node):
        base_kind = None
        for base in node.bases:
            name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", None)
            if name in WIDGETS:
                base_kind = name
                break
        if base_kind:
            w = {
                "id": "self",
                "cls": base_kind,
                "type": WIDGETS[base_kind],
                "parent": None,
                "options": {},
                "layout": None,
                "config": {},
                "line": node.lineno,
                "container": True,
                "from_class": node.name,
            }
            self.widgets.append(w)
            self.by_id["self"] = w
            self.class_stack.append(w)
            self.generic_visit(node)
            self.class_stack.pop()
            self.by_id.pop("self", None)
        else:
            self.generic_visit(node)

    def visit_Assign(self, node):
        cls = call_class(node.value)
        if cls in WIDGETS and len(node.targets) == 1:
            var = dotted_name(node.targets[0])
            self.new_widget(cls, node.value, var)
            # visita argumentos para apanhar widgets criados inline
            for a in list(node.value.args) + [k.value for k in node.value.keywords]:
                self.visit(a)
            return
        self.generic_visit(node)

    def visit_Call(self, node):
        cls = call_class(node)

        # Widget criado e descartado: tk.Label(root, text="x")
        if cls in WIDGETS:
            self.new_widget(cls, node)
            for a in list(node.args) + [k.value for k in node.keywords]:
                self.visit(a)
            return

        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            target = node.func.value

            # Encadeado: tk.Button(root, text="ok").pack(side="left")
            inner_cls = call_class(target)
            if inner_cls in WIDGETS:
                w = self.new_widget(inner_cls, target)
                for a in list(target.args) + [k.value for k in target.keywords]:
                    self.visit(a)
                self.apply_method(w, method, node)
                return

            name = dotted_name(target)
            if name and name in self.by_id:
                self.apply_method(self.by_id[name], method, node)

        self.generic_visit(node)

    # -- métodos sobre widgets --------------------------------------------

    def apply_method(self, widget, method, node):
        loop = self.loop_stack[-1] if self.loop_stack else None

        if method in LAYOUT_KEYS:
            layout = {"manager": method}
            per_instance = {}
            for kw in node.keywords:
                if kw.arg not in LAYOUT_KEYS[method]:
                    continue
                val = None
                if loop is not None:
                    seq = expand_over_loop(kw.value, loop)
                    if seq is not None:
                        per_instance[kw.arg] = seq
                        val = seq[0]
                if val is None:
                    val = literal(kw.value)
                if val is not None:
                    layout[kw.arg] = val
            if per_instance:
                layout["per_instance"] = per_instance
            widget["layout"] = layout
            return

        if method in ("config", "configure"):
            for kw in node.keywords:
                if kw.arg in OPTION_KEYS:
                    val = literal(kw.value)
                    if val is not None:
                        widget["options"][kw.arg] = val
                elif kw.arg == "menu":
                    menu = dotted_name(kw.value)
                    if menu:
                        widget["config"]["menu"] = menu
            return

        if method in CANVAS_ITEMS:
            widget["config"].setdefault("draw", []).append(
                canvas_item(method, node)
            )
            return

        if method in MENU_ADDERS:
            kind = MENU_ADDERS[method]
            entry = {"kind": kind}
            for kw in node.keywords:
                if kw.arg == "label":
                    entry["label"] = literal(kw.value)
                elif kw.arg == "menu":
                    entry["menu"] = dotted_name(kw.value)
                elif kw.arg == "accelerator":
                    entry["accelerator"] = literal(kw.value)
            widget["config"].setdefault("entries", []).append(entry)
            return

        if method == "title" and node.args:
            val = literal(node.args[0])
            if val is not None:
                widget["config"]["title"] = str(val)
            return

        if method == "geometry" and node.args:
            val = literal(node.args[0])
            if isinstance(val, str):
                widget["config"]["geometry"] = val
            return

        if method == "resizable" and len(node.args) >= 2:
            widget["config"]["resizable"] = [literal(node.args[0]), literal(node.args[1])]
            return

        if method in ("insert",) and node.args:
            # Listbox/Text/Entry: acumula conteúdo visível
            val = literal(node.args[-1])
            if isinstance(val, str):
                widget["config"].setdefault("items", []).append(val)
            return

        if method == "add" and node.args:
            # Notebook.add(frame, text="Aba")
            child = dotted_name(node.args[0])
            label = None
            for kw in node.keywords:
                if kw.arg == "text":
                    label = literal(kw.value)
            if child and child in self.by_id:
                self.by_id[child]["parent"] = widget["id"]
                self.by_id[child]["layout"] = {"manager": "tab", "text": label or child}


CANVAS_ITEM_OPTIONS = {"fill", "outline", "width", "text", "font", "anchor", "dash", "smooth"}


def canvas_item(method, node):
    """Descreve um create_* de Canvas: tipo, coordenadas e opções."""
    coords = []
    for arg in node.args:
        val = literal(arg)
        if isinstance(val, (int, float)):
            coords.append(val)
        elif isinstance(val, (list, tuple)):
            coords.extend(v for v in val if isinstance(v, (int, float)))
    item = {"kind": method[len("create_"):], "coords": coords, "options": {}}
    for kw in node.keywords:
        if kw.arg in CANVAS_ITEM_OPTIONS:
            val = literal(kw.value)
            if val is not None:
                item["options"][kw.arg] = val
    return item


def build_tree(widgets):
    """Define o pai efetivo de cada widget e devolve as raízes."""
    ids = {w["id"] for w in widgets}
    roots = [w for w in widgets if w["type"] == "Window"]
    fallback = roots[0]["id"] if roots else None

    for w in widgets:
        if w["type"] == "Window":
            continue
        if w["type"] == "Menu":
            # Menus não ocupam espaço no cliente; são ligados via config(menu=…).
            w["parent"] = None
            continue
        p = w["parent"]
        if p is None or p not in ids or p == w["id"]:
            w["parent"] = fallback
    if not roots and widgets:
        # Nenhuma janela declarada: cria uma implícita
        implicit = {
            "id": "__implicit_root", "cls": "Tk", "type": "Window", "parent": None,
            "options": {}, "layout": None, "config": {"title": "Tk (implícita)"},
            "line": 0, "container": True,
        }
        for w in widgets:
            if w["parent"] is None and w["type"] not in ("Window", "Menu"):
                w["parent"] = implicit["id"]
        widgets.insert(0, implicit)
        roots = [implicit]
    return [r["id"] for r in roots]


def analyse(source, filename="<string>"):
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return {
            "ok": False,
            "error": "Erro de sintaxe: %s" % (exc.msg,),
            "line": exc.lineno,
            "widgets": [],
            "roots": [],
        }

    parser = TkinterParser()
    parser.visit(tree)
    roots = build_tree(parser.widgets)
    return {
        "ok": True,
        "widgets": parser.widgets,
        "roots": roots,
        "warnings": parser.warnings,
    }


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--stdin":
        source = sys.stdin.read()
        name = sys.argv[2] if len(sys.argv) > 2 else "<stdin>"
    elif len(sys.argv) >= 2:
        name = sys.argv[1]
        with open(name, "r", encoding="utf-8") as f:
            source = f.read()
    else:
        print(json.dumps({"ok": False, "error": "Nenhum ficheiro indicado.",
                          "widgets": [], "roots": []}))
        return
    print(json.dumps(analyse(source, name), ensure_ascii=False))


if __name__ == "__main__":
    main()
