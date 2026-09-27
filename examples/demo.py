import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("Cadastro de Clientes")
root.geometry("420x260")
root.configure(bg="#f4f4f4")

header = tk.Label(root, text="Novo Cliente", font=("Segoe UI", 14, "bold"), bg="#f4f4f4")
header.pack(pady=(12, 8))

form = tk.Frame(root, bg="#f4f4f4")
form.pack(padx=16)

tk.Label(form, text="Nome:", bg="#f4f4f4").grid(row=0, column=0, sticky="w", pady=4)
nome = tk.Entry(form, width=28)
nome.grid(row=0, column=1, pady=4)

tk.Label(form, text="E-mail:", bg="#f4f4f4").grid(row=1, column=0, sticky="w", pady=4)
email = tk.Entry(form, width=28)
email.grid(row=1, column=1, pady=4)

tk.Label(form, text="Perfil:", bg="#f4f4f4").grid(row=2, column=0, sticky="w", pady=4)
perfil = ttk.Combobox(form, values=["Administrador", "Operador"], width=25)
perfil.grid(row=2, column=1, pady=4)

ativo = tk.Checkbutton(root, text="Cliente ativo", bg="#f4f4f4")
ativo.pack(anchor="w", padx=16, pady=6)

rodape = tk.Frame(root, bg="#f4f4f4")
rodape.pack(side="bottom", fill="x", pady=10)

tk.Button(rodape, text="Cancelar").pack(side="right", padx=8)
tk.Button(rodape, text="Salvar", bg="#3a8ddb", fg="white").pack(side="right")

root.mainloop()
