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


def literal(node):
    """Devolve o valor literal de um nó, ou None se não for estático."""
    try:
        return ast.literal_eval(node)
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
        options = {}
        for kw in node.keywords:
            if kw.arg in OPTION_KEYS:
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
        self.widgets.append(w)
        self.by_id[var] = w
        return w

    # -- visitas -----------------------------------------------------------

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
        if method in LAYOUT_KEYS:
            layout = {"manager": method}
            for kw in node.keywords:
                if kw.arg in LAYOUT_KEYS[method]:
                    val = literal(kw.value)
                    if val is not None:
                        layout[kw.arg] = val
            widget["layout"] = layout
            return

        if method in ("config", "configure"):
            for kw in node.keywords:
                if kw.arg in OPTION_KEYS:
                    val = literal(kw.value)
                    if val is not None:
                        widget["options"][kw.arg] = val
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


def build_tree(widgets):
    """Define o pai efetivo de cada widget e devolve as raízes."""
    ids = {w["id"] for w in widgets}
    roots = [w for w in widgets if w["type"] == "Window"]
    fallback = roots[0]["id"] if roots else None

    for w in widgets:
        if w["type"] == "Window":
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
            if w["parent"] is None:
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
