"""GUI: connect using existing Windows FileZilla and OpenSSH credentials."""
import tkinter as tk
from tkinter import ttk, messagebox
import bw_windows_saved as saved

def build(app):
    tab = ttk.Frame(app.tabs, padding=16)
    app.tabs.add(tab, text="  Logowania Windows  ")
    ttk.Label(tab, text="Zapisane logowania Windows", font=("DejaVu Sans", 14, "bold")).pack(anchor="w")
    ttk.Label(tab, text="FileZilla korzysta z zapisanych hasel, OpenSSH z kluczy Windows. "
              "Nie kopiujemy haseł do panelu ani do synchronizacji.", wraplength=900).pack(anchor="w")
    controls = ttk.Frame(tab)
    controls.pack(anchor="w", pady=8)
    ttk.Button(controls, text="Wczytaj", command=lambda: refresh(app)).pack(side="left")
    ttk.Button(controls, text="Przypisz dostep do domeny",
               command=lambda: app.tabs.select(app.mapping_tab)).pack(side="left", padx=(9, 0))
    app.saved_status = tk.StringVar(value="Wybierz Wczytaj.")
    ttk.Label(tab, textvariable=app.saved_status).pack(anchor="w")
    tree = ttk.Treeview(tab, columns=("name", "protocol", "host", "user", "port"),
                        show="headings", selectmode="browse")
    app.saved_tree = tree
    app.saved_data = []
    for col, width in (("name", 270), ("protocol", 100), ("host", 320),
                       ("user", 230), ("port", 70)):
        tree.heading(col, text=col.upper())
        tree.column(col, width=width, stretch=col=="host")
    tree.pack(fill="both", expand=True, pady=9)
    tree.bind("<Double-1>", lambda _event: connect(app))
    ttk.Button(tab, text="Polacz wybrany", style="Accent.TButton",
               command=lambda: connect(app)).pack(anchor="w")

def refresh(app):
    try:
        home, xml = saved.windows_config()
        items = [dict(row, mode="filezilla") for row in saved.filezilla_sites(xml)]
        for alias in saved.windows_ssh_aliases(home / ".ssh" / "config"):
            items.append(dict(name=alias, protocol="SSH", host="(config Windows)",
                              user="", port="", mode="ssh"))
        app.saved_data = items
        for iid in app.saved_tree.get_children():
            app.saved_tree.delete(iid)
        for i, item in enumerate(items):
            app.saved_tree.insert("", "end", iid=str(i), values=(
                item["name"], item["protocol"], item["host"], item["user"], item["port"]))
        app.saved_status.set("FileZilla: %d  |  SSH: %d" % (
            sum(x["mode"]=="filezilla" for x in items),
            sum(x["mode"]=="ssh" for x in items)))
    except (OSError, RuntimeError, ValueError) as exc:
        app.saved_status.set(str(exc))

def connect(app):
    select = app.saved_tree.selection()
    if not select:
        return
    row = app.saved_data[int(select[0])]
    try:
        if row["mode"] == "filezilla":
            saved.open_filezilla_site(row)
        else:
            saved.connect_windows_ssh(row["name"])
        app.saved_status.set("Uruchomiono: "+row["name"])
    except (OSError, RuntimeError, ValueError) as exc:
        messagebox.showerror("Polaczenie", str(exc), parent=app.root)
