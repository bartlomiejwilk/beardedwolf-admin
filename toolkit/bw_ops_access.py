"""Local review screen for endpoint metadata. Never imports saved secrets."""
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import bw_access
import bw_filezilla
import bw_servers


def build(app):
    tab = ttk.Frame(app.tabs, padding=16)
    app.tabs.add(tab, text="  Dostępy / import  ")
    ttk.Label(tab, text="Inwentaryzacja zapisanych połączeń",
              font=("DejaVu Sans", 14, "bold")).pack(anchor="w", pady=(0, 7))
    ttk.Label(tab, text="Tylko metadane: alias, protokół, host, port, login. "
              "Bez kluczy, haseł i połączeń sieciowych. Dane urzędowe pozostają "
              "w środowisku urzędu, jeśli nie ma zgody na ich przenoszenie.",
              wraplength=1050).pack(anchor="w", fill="x", pady=(0, 9))

    toolbar = ttk.Frame(tab)
    toolbar.pack(fill="x", pady=(0, 10))
    ttk.Button(toolbar, text="Eksport SSH z tego Kali",
               command=lambda: export_local(app)).pack(side="left", padx=(0, 9))
    ttk.Button(toolbar, text="Porównaj eksport JSON",
               command=lambda: read_export(app)).pack(side="left", padx=(0, 9))
    ttk.Button(toolbar, text="Odczytaj eksport FileZilla XML",
               command=lambda: read_filezilla(app)).pack(side="left")

    app.access_hint = tk.StringVar(value="Brak wczytanego pliku. Żadne profile nie zostały zmienione.")
    ttk.Label(tab, textvariable=app.access_hint, wraplength=1080).pack(
        anchor="w", fill="x", pady=(0, 8))
    cols = ("state", "alias", "protocol", "host", "user", "port", "source")
    tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
    for key, text, width in (
        ("state", "WYNIK", 115), ("alias", "ALIAS", 140),
        ("protocol", "PROTOKÓŁ", 110), ("host", "SERWER", 290),
        ("user", "LOGIN", 130), ("port", "PORT", 70),
        ("source", "ŹRÓDŁO", 150)
    ):
        tree.heading(key, text=text)
        tree.column(key, width=width, stretch=(key == "host"))
    tree.pack(fill="both", expand=True)
    app.access_list = tree
    app.access_candidates = []
    actions = ttk.Frame(tab)
    actions.pack(fill="x", pady=(10, 0))
    ttk.Button(actions, text="Dodaj wybrany NOWY profil SSH",
               style="Accent.TButton",
               command=lambda: import_selected(app)).pack(side="left")
    ttk.Label(actions, text="Import nie nadpisuje istniejących profili ani kluczy. "
              "SFTP / FTP wymagają oddzielnej konfiguracji.",
              wraplength=700).pack(side="right")


def show(app, records, origin):
    app.access_candidates = records
    for iid in app.access_list.get_children():
        app.access_list.delete(iid)
    reviewed = bw_access.inspect(records)
    for i, (candidate, result) in enumerate(zip(records, reviewed)):
        app.access_list.insert("", "end", iid=str(i), values=(
            result["state"], result.get("alias") or "",
            candidate.get("protocol", ""), result.get("host") or "",
            result.get("user") or "", result.get("port") or "",
            result.get("source") or origin
        ))
    counts = {}
    for row in reviewed:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    app.access_hint.set(
        "%s • Wpisów: %d • Nowych SSH: %d • Konfliktów: %d • "
        "Niekompletnych lub innych protokołów: %d" %
        (origin, len(records), counts.get("NEW", 0),
         counts.get("CONFLICT", 0),
         counts.get("INCOMPLETE", 0) + counts.get("SKIP_PROTOCOL", 0))
    )


def export_local(app):
    path = filedialog.asksaveasfilename(
        parent=app.root, title="Lokalny eksport SSH bez haseł",
        defaultextension=".json", filetypes=[("JSON", "*.json")],
        initialfile="beardedwolf-ssh-local.json"
    )
    if not path:
        return
    from pathlib import Path
    target = Path(path)
    if target.exists():
        messagebox.showwarning("Plik już istnieje", "Nie nadpisuję istniejącego pliku.",
                               parent=app.root)
        return
    try:
        records = bw_access.inventory()
        payload = {"schema": 1, "profiles": records}
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        target.chmod(0o600)
        show(app, records, "Lokalne Kali")
    except (OSError, ValueError) as exc:
        messagebox.showerror("Eksport", str(exc), parent=app.root)


def read_export(app):
    file = filedialog.askopenfilename(
        parent=app.root, title="Wczytaj WYŁĄCZNIE metadane połączeń",
        filetypes=[("JSON", "*.json")]
    )
    if not file:
        return
    try:
        from pathlib import Path
        payload = json.loads(Path(file).read_text(encoding="utf-8-sig"))
        if payload.get("schema") != 1 or not isinstance(payload.get("profiles"), list):
            raise ValueError("Niezgodny format JSON.")
        show(app, payload["profiles"], "Import JSON")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        messagebox.showerror("Import", str(exc), parent=app.root)


def read_filezilla(app):
    file = filedialog.askopenfilename(
        parent=app.root, title="Eksport FileZilla bez kopiowania haseł",
        filetypes=[("FileZilla XML", "*.xml")]
    )
    if not file:
        return
    try:
        entries = bw_filezilla.read_export(file)
        records = [dict(alias=row["name"], host=row["host"],
                        user=row["user"], port=row["port"],
                        protocol=row["access"], source="filezilla")
                   for row in entries]
        show(app, records, "FileZilla (bez haseł)")
    except (OSError, ValueError) as exc:
        messagebox.showerror("FileZilla", str(exc), parent=app.root)


def import_selected(app):
    selection = app.access_list.selection()
    if not selection:
        messagebox.showinfo("Import", "Wybierz pojedynczy profil.", parent=app.root)
        return
    idx = int(selection[0])
    row = app.access_candidates[idx]
    status = app.access_list.set(selection[0], "state")
    if status != "NEW":
        messagebox.showwarning("Profil niegotowy",
                               "Można dodać tylko nowy, kompletny profil SSH. "
                               "Pozostałe wpisy wymagają weryfikacji.",
                               parent=app.root)
        return
    if not messagebox.askyesno(
        "Potwierdź import do współdzielonego rejestru",
        "Alias: %s\nSerwer: %s\nLogin: %s\nPort: %s\n\n"
        "Czy potwierdzasz uprawnienia i zgodę na synchronizację "
        "tych danych pomiędzy PC-Wilk i Lenovo? "
        "Klucze prywatne nie będą kopiowane." %
        (row["alias"], row["host"], row["user"], row["port"]),
        parent=app.root
    ):
        return
    try:
        bw_servers.add_profile(row["alias"], row["host"], row["user"], row["port"])
        app.refresh_servers()
        show(app, app.access_candidates, "Po imporcie")
    except (OSError, RuntimeError, ValueError) as exc:
        messagebox.showerror("Nie zapisano profilu", str(exc), parent=app.root)
