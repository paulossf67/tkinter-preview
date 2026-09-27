"""Testes do analisador estático. Correr com:  python -m unittest discover tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser_tk import analyse  # noqa: E402


def widgets_by_id(result):
    return {w["id"]: w for w in result["widgets"]}


def find(result, cls):
    return [w for w in result["widgets"] if w["cls"] == cls]


class TestBasics(unittest.TestCase):
    def test_window_title_and_geometry(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'root.title("Olá")\n'
            'root.geometry("320x240")\n'
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["roots"], ["root"])
        root = widgets_by_id(r)["root"]
        self.assertEqual(root["config"]["title"], "Olá")
        self.assertEqual(root["config"]["geometry"], "320x240")

    def test_syntax_error_is_reported(self):
        r = analyse("root = tk.Tk(\n")
        self.assertFalse(r["ok"])
        self.assertIn("sintaxe", r["error"])

    def test_no_widgets(self):
        r = analyse("x = 1 + 2\nprint(x)\n")
        self.assertTrue(r["ok"])
        self.assertEqual(r["widgets"], [])

    def test_bare_import_style(self):
        r = analyse('from tkinter import *\nroot = Tk()\nLabel(root, text="oi").pack()\n')
        labels = find(r, "Label")
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]["options"]["text"], "oi")
        self.assertEqual(labels[0]["layout"]["manager"], "pack")
        self.assertEqual(labels[0]["parent"], "root")


class TestLayout(unittest.TestCase):
    def test_pack_options(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'b = tk.Button(root, text="Ok")\n'
            'b.pack(side=tk.LEFT, fill="both", expand=True, padx=(4, 8))\n'
        )
        layout = widgets_by_id(r)["b"]["layout"]
        self.assertEqual(layout["side"], "left")
        self.assertEqual(layout["fill"], "both")
        self.assertTrue(layout["expand"])
        self.assertEqual(layout["padx"], [4, 8])

    def test_grid_and_place(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'a = tk.Label(root, text="A")\n'
            'a.grid(row=2, column=1, columnspan=3, sticky="we")\n'
            'b = tk.Label(root, text="B")\n'
            'b.place(x=10, y=20, relwidth=0.5)\n'
        )
        by = widgets_by_id(r)
        self.assertEqual(by["a"]["layout"]["row"], 2)
        self.assertEqual(by["a"]["layout"]["columnspan"], 3)
        self.assertEqual(by["a"]["layout"]["sticky"], "we")
        self.assertEqual(by["b"]["layout"]["manager"], "place")
        self.assertEqual(by["b"]["layout"]["relwidth"], 0.5)

    def test_chained_creation_and_layout(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'tk.Button(root, text="X").pack(side="right")\n'
        )
        btn = find(r, "Button")[0]
        self.assertEqual(btn["options"]["text"], "X")
        self.assertEqual(btn["layout"]["side"], "right")


class TestClasses(unittest.TestCase):
    def test_class_based_app(self):
        r = analyse(
            'import tkinter as tk\n'
            'class App(tk.Tk):\n'
            '    def __init__(self):\n'
            '        super().__init__()\n'
            '        self.title("Classe")\n'
            '        self.lbl = tk.Label(self, text="Oi")\n'
            '        self.lbl.pack()\n'
        )
        by = widgets_by_id(r)
        self.assertEqual(r["roots"], ["self"])
        self.assertEqual(by["self"]["from_class"], "App")
        self.assertEqual(by["self"]["config"]["title"], "Classe")
        self.assertEqual(by["self.lbl"]["parent"], "self")

    def test_frame_subclass_gets_fallback_root(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'class Painel(tk.Frame):\n'
            '    def __init__(self, master):\n'
            '        super().__init__(master)\n'
            '        tk.Label(self, text="dentro").pack()\n'
        )
        by = widgets_by_id(r)
        self.assertEqual(by["self"]["type"], "Frame")
        self.assertEqual(by["self"]["parent"], "root")
        self.assertEqual(find(r, "Label")[0]["parent"], "self")


class TestLoops(unittest.TestCase):
    def test_range_loop_repeats_and_expands_row(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'for i in range(3):\n'
            '    tk.Label(root, text=f"Linha {i}").grid(row=i, column=0)\n'
        )
        lbl = find(r, "Label")[0]
        self.assertEqual(lbl["repeat"], 3)
        self.assertEqual(lbl["per_instance"]["text"], ["Linha 0", "Linha 1", "Linha 2"])
        self.assertEqual(lbl["layout"]["per_instance"]["row"], [0, 1, 2])

    def test_list_loop(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'for nome in ["Ana", "Bruno"]:\n'
            '    tk.Button(root, text=nome).pack()\n'
        )
        btn = find(r, "Button")[0]
        self.assertEqual(btn["repeat"], 2)
        self.assertEqual(btn["per_instance"]["text"], ["Ana", "Bruno"])

    def test_enumerate_loop(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'for i, nome in enumerate(["A", "B", "C"]):\n'
            '    tk.Label(root, text=nome).grid(row=i, column=0)\n'
        )
        lbl = find(r, "Label")[0]
        self.assertEqual(lbl["repeat"], 3)
        self.assertEqual(lbl["per_instance"]["text"], ["A", "B", "C"])
        self.assertEqual(lbl["layout"]["per_instance"]["row"], [0, 1, 2])

    def test_dynamic_loop_warns_and_draws_once(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'for item in carregar():\n'
            '    tk.Label(root, text="x").pack()\n'
        )
        lbl = find(r, "Label")[0]
        self.assertNotIn("repeat", lbl)
        self.assertTrue(any("for" in w for w in r["warnings"]))


class TestConditionals(unittest.TestCase):
    def test_if_body_is_flagged(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'if admin:\n'
            '    tk.Button(root, text="Apagar").pack()\n'
            'else:\n'
            '    tk.Label(root, text="Sem permissão").pack()\n'
        )
        self.assertTrue(find(r, "Button")[0]["conditional"])
        self.assertTrue(find(r, "Label")[0]["conditional"])

    def test_main_guard_is_not_conditional(self):
        r = analyse(
            'import tkinter as tk\n'
            'if __name__ == "__main__":\n'
            '    root = tk.Tk()\n'
            '    tk.Label(root, text="oi").pack()\n'
        )
        self.assertNotIn("conditional", find(r, "Label")[0])


class TestMenusAndCanvas(unittest.TestCase):
    def test_menu_tree(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'menubar = tk.Menu(root)\n'
            'arquivo = tk.Menu(menubar, tearoff=0)\n'
            'arquivo.add_command(label="Abrir")\n'
            'arquivo.add_separator()\n'
            'arquivo.add_command(label="Sair")\n'
            'menubar.add_cascade(label="Arquivo", menu=arquivo)\n'
            'root.config(menu=menubar)\n'
        )
        by = widgets_by_id(r)
        self.assertEqual(by["root"]["config"]["menu"], "menubar")
        self.assertIsNone(by["menubar"]["parent"])
        cascade = by["menubar"]["config"]["entries"][0]
        self.assertEqual(cascade["label"], "Arquivo")
        self.assertEqual(cascade["menu"], "arquivo")
        entries = by["arquivo"]["config"]["entries"]
        self.assertEqual([e["kind"] for e in entries], ["command", "separator", "command"])
        self.assertEqual(entries[0]["label"], "Abrir")

    def test_canvas_items(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'c = tk.Canvas(root, width=200, height=100)\n'
            'c.pack()\n'
            'c.create_rectangle(10, 10, 60, 40, fill="red")\n'
            'c.create_text(80, 20, text="Oi")\n'
            'c.create_line(0, 0, 100, 100, width=2)\n'
        )
        draw = widgets_by_id(r)["c"]["config"]["draw"]
        self.assertEqual([d["kind"] for d in draw], ["rectangle", "text", "line"])
        self.assertEqual(draw[0]["coords"], [10, 10, 60, 40])
        self.assertEqual(draw[0]["options"]["fill"], "red")
        self.assertEqual(draw[1]["options"]["text"], "Oi")


class TestMisc(unittest.TestCase):
    def test_notebook_tabs(self):
        r = analyse(
            'import tkinter as tk\n'
            'from tkinter import ttk\n'
            'root = tk.Tk()\n'
            'nb = ttk.Notebook(root)\n'
            'nb.pack()\n'
            'aba = ttk.Frame(nb)\n'
            'nb.add(aba, text="Geral")\n'
        )
        by = widgets_by_id(r)
        self.assertEqual(by["aba"]["parent"], "nb")
        self.assertEqual(by["aba"]["layout"], {"manager": "tab", "text": "Geral"})

    def test_implicit_root_when_no_window(self):
        r = analyse('import tkinter as tk\nlbl = tk.Label(text="sem janela")\nlbl.pack()\n')
        self.assertEqual(r["roots"], ["__implicit_root"])
        self.assertEqual(widgets_by_id(r)["lbl"]["parent"], "__implicit_root")

    def test_customtkinter(self):
        r = analyse(
            'import customtkinter as ctk\n'
            'app = ctk.CTk()\n'
            'ctk.CTkButton(app, text="Ir", fg_color="#123456").pack()\n'
        )
        btn = find(r, "CTkButton")[0]
        self.assertEqual(btn["type"], "Button")
        self.assertEqual(btn["options"]["fg_color"], "#123456")

    def test_insert_content(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'lb = tk.Listbox(root)\n'
            'lb.insert("end", "Primeiro")\n'
            'lb.insert("end", "Segundo")\n'
        )
        self.assertEqual(
            widgets_by_id(r)["lb"]["config"]["items"], ["Primeiro", "Segundo"]
        )

    def test_fstring_with_unknown_value(self):
        r = analyse(
            'import tkinter as tk\n'
            'root = tk.Tk()\n'
            'tk.Label(root, text=f"Total: {total}").pack()\n'
        )
        self.assertEqual(find(r, "Label")[0]["options"]["text"], "Total: {...}")


if __name__ == "__main__":
    unittest.main()
