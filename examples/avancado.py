"""Exemplo com menu, Canvas, Notebook, ciclo `for` e um ramo condicional."""

import tkinter as tk
from tkinter import ttk

PRODUTOS = ["Filamento PLA", "Filamento ABS", "Resina"]
admin = False

root = tk.Tk()
root.title("Painel de Produção")
root.geometry("520x360")

menubar = tk.Menu(root)

arquivo = tk.Menu(menubar, tearoff=0)
arquivo.add_command(label="Novo", accelerator="Ctrl+N")
arquivo.add_command(label="Abrir…", accelerator="Ctrl+O")
arquivo.add_separator()
arquivo.add_command(label="Sair")
menubar.add_cascade(label="Arquivo", menu=arquivo)

ajuda = tk.Menu(menubar, tearoff=0)
ajuda.add_command(label="Sobre")
menubar.add_cascade(label="Ajuda", menu=ajuda)

root.config(menu=menubar)

abas = ttk.Notebook(root)
abas.pack(fill="both", expand=True, padx=8, pady=8)

# --- aba 1: lista gerada num ciclo ---
estoque = ttk.Frame(abas)
abas.add(estoque, text="Estoque")

for i, produto in enumerate(PRODUTOS):
    tk.Label(estoque, text=produto, anchor="w").grid(row=i, column=0, sticky="w", pady=2)
    tk.Entry(estoque, width=8).grid(row=i, column=1, padx=6)

if admin:
    tk.Button(estoque, text="Apagar tudo", bg="#c0392b", fg="white").grid(row=9, column=0)

# --- aba 2: desenho num Canvas ---
grafico = ttk.Frame(abas)
abas.add(grafico, text="Gráfico")

tela = tk.Canvas(grafico, width=420, height=200, bg="white")
tela.pack(padx=6, pady=6)
tela.create_line(30, 170, 400, 170, width=2)
tela.create_line(30, 170, 30, 20, width=2)
tela.create_rectangle(60, 110, 100, 170, fill="#3a8ddb")
tela.create_rectangle(130, 70, 170, 170, fill="#3a8ddb")
tela.create_rectangle(200, 40, 240, 170, fill="#3a8ddb")
tela.create_oval(330, 50, 380, 100, fill="#f1c40f")
tela.create_text(215, 12, text="Produção por semana")

rodape = tk.Frame(root)
rodape.pack(side="bottom", fill="x", pady=(0, 8), padx=8)
ttk.Progressbar(rodape).pack(side="left")
tk.Button(rodape, text="Fechar").pack(side="right")
tk.Button(rodape, text="Exportar").pack(side="right", padx=6)

root.mainloop()
