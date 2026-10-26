"""Read-only, explicitly authorized WordPress path discovery in GUI."""
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import bw_fleet
import bw_integrity
import bw_paths
import bw_servers


def build(app):
    tab = ttk.Frame(app.tabs, padding=16)
    app.tabs.add(tab, text="  Katalogi WordPress  ")
    ttk.Label(tab, text="Weryfikacja katalogów instalacji",
              font=("DejaVu Sans", 14, "bold")).pack(anchor="w", pady=(0, 7))
    ttk.Label(tab, text="Znajduje wyłącznie nazwy katalogów przez potwierdzone SSH "
              "lub FTPS. Nie odczytuje wp-config.php, nie zmienia plików "
              "i nie zapisuje automatycznie przypisań.",
              wraplength=1030).pack(fill="x", anchor="w", pady=(0, 12))
    controls = ttk.Frame(tab)
    controls.pack(fill="x", pady=(0, 9))
    ttk.Label(controls, text="Serwis WordPress:").pack(side="left", padx=(0, 8))
    app.paths_domain = tk.StringVar(value="")
    choice = ttk.Combobox(controls, textvariable=app.paths_domain,
                          state="readonly", width=42)
    choice.pack(side="left", padx=(0, 8))
    app.paths_domain_combo = choice
    ttk.Button(controls, text="Odśwież serwisy",
               command=lambda: refresh_sites(app)).pack(side="left")
    actions = ttk.Frame(tab)
    actions.pack(fill="x", pady=(0, 10))
    app.paths_scan = ttk.Button(
        actions, text="Sprawdź katalogi przez SSH",
        style="Accent.TButton", command=lambda: scan(app, "ssh")
    )
    app.paths_scan.pack(side="left", padx=(0, 9))
    ttk.Button(actions, text="FTPS, jeśli SSH niedostępne",
               command=lambda: scan(app, "ftps")).pack(side="left")
    app.paths_hint = tk.StringVar(value="Wybierz serwis z potwierdzonym zakresem.")
    ttk.Label(tab, textvariable=app.paths_hint, wraplength=1030).pack(
        anchor="w", fill="x", pady=(0, 7))
    tree = ttk.Treeview(tab, columns=("path",), show="headings",
                        selectmode="browse")
    tree.heading("path", text="ZNALEZIONY KATALOG WORDPRESS")
    tree.column("path", width=800)
    tree.pack(fill="both", expand=True)
    app.paths_table = tree
    app.paths_last_domain = None
    ttk.Button(tab, text="Przypisz zaznaczony katalog do domeny",
               command=lambda: confirm_path(app)).pack(anchor="w", pady=(9, 0))
    refresh_sites(app)


def refresh_sites(app):
    try:
        sites = [s["domain"] for s in bw_fleet.inventory()["sites"]
                 if s.get("type") == "wordpress" and s.get("authorized")]
    except (OSError, ValueError) as exc:
        app.paths_hint.set(str(exc))
        return
    sites = sorted(sites)
    app.paths_domain_combo.configure(values=sites)
    if app.paths_domain.get() not in sites:
        app.paths_domain.set(sites[0] if sites else "")


def scan(app, protocol):
    domain = app.paths_domain.get()
    if not domain:
        return
    site = bw_fleet.get_site(domain)
    if not site.get("authorized"):
        messagebox.showwarning("Brak uprawnienia",
                               "Najpierw potwierdź zakres dla tego serwisu.",
                               parent=app.root)
        return
    if protocol == "ssh":
        alias = site.get("ssh_alias")
        if not alias:
            messagebox.showwarning("Brak SSH", "Wpis nie ma profilu SSH.",
                                   parent=app.root)
            return
        result = bw_integrity.profile_endpoint_check(
            site, bw_servers.load_profiles()
        )
        if result and result[0] == "BŁĄD":
            messagebox.showerror("Niezgodny serwer SSH", result[1], parent=app.root)
            return
        label = "SSH: " + alias
        kwargs = {}
        target = alias
    else:
        info = bw_fleet.hosting_info(site)
        if info["access"] != "ftps" or not info["host"]:
            messagebox.showwarning(
                "FTPS niepotwierdzone",
                "Najpierw zweryfikuj protokół FTPS i adres w danych hostingowych. "
                "Nie wysyłamy haseł przez nieszyfrowany FTP.",
                parent=app.root
            )
            return
        username = info.get("user") or simpledialog.askstring(
            "FTPS", "Login FTPS:", parent=app.root
        )
        if not username:
            return
        password = simpledialog.askstring(
            "Hasło tylko do sesji FTPS", "Hasło FTPS (nie będzie zapisywane):",
            show="*", parent=app.root
        )
        if password is None:
            return
        label = "FTPS: " + info["host"]
        target = info["host"]
        kwargs = {"user": username, "password": password}
    if not messagebox.askyesno(
        "Autoryzacja odczytu",
        "Domena: %s\nMetoda: %s\n\nWykonać ograniczony odczyt nazw katalogów "
        "w zakresie dostępnego konta? Żadnych zmian na serwerze." %
        (domain, label), parent=app.root
    ):
        return
    app.paths_scan.configure(state="disabled")
    app.paths_hint.set("Trwa odczyt nazw katalogów przez %s..." % label)
    def worker():
        try:
            if protocol == "ssh":
                result = bw_paths.ssh_roots(target, depth=4)
            else:
                result = bw_paths.ftps_roots(target, kwargs["user"],
                                             kwargs["password"], depth=3)
            err = None
        except Exception as exc:
            result, err = [], str(exc)
        app.root.after(0, lambda: finished(app, domain, result, err))
    threading.Thread(target=worker, daemon=True).start()


def finished(app, domain, paths, error):
    app.paths_scan.configure(state="normal")
    app.paths_last_domain = domain if not error else None
    for iid in app.paths_table.get_children():
        app.paths_table.delete(iid)
    if error:
        app.paths_hint.set("Nie udało się: " + error)
        return
    for i, path in enumerate(paths):
        app.paths_table.insert("", "end", iid=str(i), values=(path,))
    app.paths_hint.set("Domena: %s. Kandydatów: %d. "
                       "Sprawdź właściwy katalog przed przypisaniem." %
                       (domain, len(paths)))


def confirm_path(app):
    domain = app.paths_domain.get()
    if domain != app.paths_last_domain:
        messagebox.showwarning("Dane nieaktualne",
                               "Wykonaj odczyt dla bieżącej domeny.",
                               parent=app.root)
        return
    selection = app.paths_table.selection()
    if not selection:
        return
    path = app.paths_table.set(selection[0], "path")
    site = bw_fleet.get_site(domain)
    alias = site.get("ssh_alias")
    if not alias:
        messagebox.showwarning("Nie przypisano",
                               "Katalog można przypisać po skonfigurowaniu SSH.",
                               parent=app.root)
        return
    if not messagebox.askyesno(
        "Zatwierdzenie katalogu WordPress",
        "Domena: %s\nProfil: %s\nKatalog: %s\n\n"
        "Czy potwierdzasz, że wybrana instalacja obsługuje wskazaną domenę?" %
        (domain, alias, path), parent=app.root
    ):
        return
    try:
        bw_fleet.assign_ssh(domain, alias, path)
        app.refresh_fleet()
        app.paths_hint.set("Zapisano przypisanie %s → %s" % (domain, path))
    except (OSError, ValueError, RuntimeError) as exc:
        messagebox.showerror("Nie zapisano", str(exc), parent=app.root)
