"""Assign current Windows FileZilla FTP/SFTP and shared SSH profiles to domains.

The operator chooses each mapping. No automatic server logins or filesystem
access; passwords remain in their original clients. Updates existing shared
sites.json only after explicit confirmation.
"""
import tkinter as tk
import threading
from tkinter import messagebox, ttk

import bw_fleet
import bw_integrity
import bw_servers
import bw_windows_saved
import bw_ssh_direct


def _provider(host):
    host = host.lower()
    if host.endswith(".hosting.ovh.net"):
        return "OVHcloud"
    if host.endswith(".nazwa.pl"):
        return "nazwa.pl"
    if host.endswith(".cyber-folks.pl"):
        return "cyber_Folks"
    return "nieustalony"


def build(app):
    tab = ttk.Frame(app.tabs, padding=16)
    app.tabs.add(tab, text="  Powiazania  ")
    app.mapping_tab = tab
    ttk.Label(tab, text="Powiaz domeny z zapisanymi polaczeniami",
              font=("DejaVu Sans", 14, "bold")).pack(anchor="w")
    ttk.Label(tab, text=(
        "Wybierz domene i zapisane polaczenie. SSH zostaje w profilu SSH, "
        "FTP/SFTP w danych hostingu. Nic nie jest przypisywane automatycznie "
        "ani nie sa kopiowane hasla. Stare eksporty nie sa wykorzystywane."
    ), wraplength=1100).pack(anchor="w", fill="x", pady=(3, 10))
    control = ttk.Frame(tab)
    control.pack(fill="x", pady=(0, 9))
    ttk.Button(control, text="Odswiez domeny i FileZille",
               command=lambda: refresh(app)).pack(side="left")
    app.mapping_summary = tk.StringVar(value="")
    ttk.Label(control, textvariable=app.mapping_summary).pack(side="left", padx=(14, 0))
    tree = ttk.Treeview(tab, columns=("domain", "ssh", "access", "host"),
                        show="headings", selectmode="browse", height=12)
    for key, label, width in (
        ("domain", "DOMENA", 290), ("ssh", "SSH", 135),
        ("access", "FTP / SFTP", 140), ("host", "HOSTING / SERWER", 450)
    ):
        tree.heading(key, text=label)
        tree.column(key, width=width, stretch=(key == "domain" or key == "host"))
    tree.pack(fill="both", expand=True)
    app.mapping_sites = tree
    row = ttk.Frame(tab)
    row.pack(fill="x", pady=(12, 6))
    ttk.Label(row, text="Zapisane polaczenie:").pack(side="left", padx=(0, 9))
    app.mapping_pick = tk.StringVar(value="")
    app.mapping_combo = ttk.Combobox(row, textvariable=app.mapping_pick,
                                     state="readonly", width=75)
    app.mapping_combo.pack(side="left", fill="x", expand=True)
    ttk.Button(row, text="Zapisz powiazanie",
               style="Accent.TButton",
               command=lambda: assign(app)).pack(side="left", padx=(12, 0))
    ttk.Button(row, text="Test SSH bez aliasu",
               command=lambda: test_selected(app)).pack(side="left", padx=(8, 0))
    ttk.Button(row, text="Otworz wybrane logowanie",
               command=lambda: connect_selected(app)).pack(side="left", padx=(8, 0))
    app.mapping_hint = tk.StringVar(value="Najpierw wybierz domene i polaczenie.")
    ttk.Label(tab, textvariable=app.mapping_hint, wraplength=1100).pack(
        anchor="w", fill="x", pady=(4, 0)
    )
    app.mapping_sites.bind("<<TreeviewSelect>>",
                           lambda _evt: suggest(app))
    refresh(app)


def refresh(app):
    try:
        sites = bw_fleet.inventory()["sites"]
        ssh = bw_servers.load_profiles()
        candidates = []
        for p in ssh:
            candidates.append(("SSH: %s | %s@%s:%s" %
                               (p["alias"], p["user"], p["host"], p["port"]),
                               {"kind": "ssh", "alias": p["alias"], "profile": p}))
        try:
            _, xml = bw_windows_saved.windows_config()
            saved = bw_windows_saved.filezilla_sites(xml)
        except (RuntimeError, OSError):
            saved = []
        for p in saved:
            if p["protocol"] not in ("FTP", "SFTP", "FTPS"):
                continue
            candidates.append((
                "%s: %s | %s@%s:%s" %
                (p["protocol"], p["name"], p["user"], p["host"], p["port"]),
                {"kind": "filezilla", "entry": p}
            ))
        app.mapping_candidates = dict(candidates)
        app.mapping_combo.configure(values=[label for label, _ in candidates])
        selected = app.mapping_sites.selection()
        prior = app.mapping_sites.set(selected[0], "domain") if selected else None
        for iid in app.mapping_sites.get_children():
            app.mapping_sites.delete(iid)
        for site in sorted(sites, key=lambda s: s["domain"]):
            hosting = bw_fleet.hosting_info(site)
            app.mapping_sites.insert("", "end", iid=site["domain"], values=(
                site["domain"], site.get("ssh_alias") or "(brak)",
                hosting["access"], hosting["host"] or "(brak)"
            ))
        if prior and app.mapping_sites.exists(prior):
            app.mapping_sites.selection_set(prior)
            app.mapping_sites.see(prior)
        app.mapping_summary.set(
            "%d domen | %d profili SSH | %d sesji FileZilla" %
            (len(sites), len(ssh), len(saved)))
        app.mapping_hint.set("Wybierz wpis; bez testow sieciowych.")
    except (OSError, ValueError, RuntimeError) as exc:
        app.mapping_hint.set("Blad odczytu: " + str(exc))


def suggest(app):
    selection = app.mapping_sites.selection()
    if not selection:
        return
    domain = selection[0]
    site = bw_fleet.get_site(domain)
    hosting = bw_fleet.hosting_info(site)
    # Suggest only an already-assigned SSH alias or an EXACT endpoint match.
    # Never infer destination from a similar domain name.
    for name, item in app.mapping_candidates.items():
        if item["kind"] == "ssh" and item["alias"] == site.get("ssh_alias"):
            app.mapping_pick.set(name)
            app.mapping_hint.set("Zapisany profil SSH. Mozesz wybrac FTP/SFTP oddzielnie.")
            return
        if item["kind"] == "filezilla":
            p = item["entry"]
            if (hosting["host"] and hosting["host"].lower() == p["host"].lower()
                    and hosting["port"] == int(p["port"])
                    and hosting["user"] == p["user"]):
                app.mapping_pick.set(name)
                app.mapping_hint.set("Zgodne metadane juz zapisane w hostingu.")
                return
    app.mapping_pick.set("")
    app.mapping_hint.set("Brak jednoznacznego dopasowania. Wybierz recznie.")


def assign(app):
    selected = app.mapping_sites.selection()
    chosen = app.mapping_pick.get()
    if not selected or chosen not in app.mapping_candidates:
        messagebox.showwarning("Brak wyboru", "Wybierz domene i polaczenie.",
                               parent=app.root)
        return
    domain = selected[0]
    site = bw_fleet.get_site(domain)
    if site.get("type") == "przekierowanie":
        messagebox.showwarning(
            "Przekierowanie", "To domena przekierowujaca. Najpierw zweryfikuj, "
            "czy ma odrebna instalacje lub konto serwera.", parent=app.root
        )
        return
    info = app.mapping_candidates[chosen]
    if info["kind"] == "ssh":
        profile = info["profile"]
        new_alias = info["alias"]
        candidate = dict(site, ssh_alias=new_alias)
        warning = bw_integrity.profile_endpoint_check(
            candidate, bw_servers.load_profiles())
        if warning and warning[0] == "BŁĄD":
            messagebox.showerror("Nieprawidlowy serwer", warning[1],
                                 parent=app.root)
            return
        previous_path = site.get("wp_root")
        path = previous_path if site.get("ssh_alias") == new_alias else None
        note = ("\nUWAGA: poprzedni katalog WordPress zostanie wyczyszczony."
                if previous_path and not path else "")
        message = ("Domena: %s\nProfil SSH: %s\nHost: %s\nLogin: %s\nPort: %s%s"
                   % (domain, new_alias, profile["host"], profile["user"],
                      profile["port"], note))
        if warning:
            message += "\n\n" + warning[1]
        if not messagebox.askyesno("Potwierdz SSH", message, parent=app.root):
            return
        bw_fleet.assign_ssh(domain, new_alias, path)
    else:
        p = info["entry"]
        protocol = p["protocol"].lower()
        old = bw_fleet.hosting_info(site)
        message = ("Domena: %s\n\nSTARE: %s | %s | %s\nNOWE: %s | %s:%s | %s\n\n"
                   "Zastapic TYLKO dane FTP/SFTP hostingu? Profil SSH pozostanie."
                   % (domain, old["access"], old["host"], old["user"],
                      protocol.upper(), p["host"], p["port"], p["user"]))
        if protocol == "ftp":
            message += "\nSzyfrowanie FTP nalezy zweryfikowac oddzielnie."
        if not messagebox.askyesno("Potwierdz polaczenie", message,
                                   parent=app.root):
            return
        bw_fleet.update_hosting(domain, _provider(p["host"]), protocol,
                                p["host"], int(p["port"]), p["user"])
    refresh(app)
    app.refresh_fleet()
    app.mapping_hint.set("Zapisano powiazanie dla: " + domain)


def test_selected(app):
    """Single opt-in public-key check of selected SSH/SFTP host/user/port."""
    chosen = app.mapping_pick.get()
    entry = getattr(app, "mapping_candidates", {}).get(chosen)
    if not entry:
        messagebox.showwarning("Brak polaczenia", "Wybierz SSH lub SFTP.",
                               parent=app.root)
        return
    if entry["kind"] == "ssh":
        p = entry["profile"]
        host, user, port = p["host"], p["user"], p["port"]
    else:
        p = entry["entry"]
        if p["protocol"] != "SFTP":
            messagebox.showwarning("To nie jest SSH",
                                   "Dla FTP/FTPS sprawdz logowanie w FileZilli.",
                                   parent=app.root)
            return
        host, user, port = p["host"], p["user"], p["port"]
    text = ("Testowac raz bezposrednie uwierzytelnienie Windows SSH "
            "BEZ aliasow, hasla i interakcji?\\n\\n%s@%s:%s\\n\\n"
            "Brak poprawnego klucza nie oznacza nieaktywnego konta." %
            (user, host, port))
    if not messagebox.askyesno("Test SSH bez aliasu", text, parent=app.root):
        return
    app.mapping_hint.set("Trwa jednorazowy test SSH %s@%s:%s" %
                         (user, host, port))
    def run():
        try:
            status, detail = bw_ssh_direct.test_direct(host, user, port)
        except (OSError, RuntimeError, ValueError) as exc:
            status, detail = "BLAD", str(exc)
        def completed():
            app.mapping_hint.set("SSH %s@%s:%s - %s: %s" %
                                 (user, host, port, status, detail))
        try:
            app.root.after(0, completed)
        except RuntimeError:
            pass
    threading.Thread(target=run, daemon=True).start()


def connect_selected(app):
    """Open original FileZilla saved credentials or Windows SSH directly."""
    name = app.mapping_pick.get()
    entry = getattr(app, "mapping_candidates", {}).get(name)
    if entry is None:
        return
    if not messagebox.askyesno("Otworz polaczenie",
                               "Uruchomic zapisane polaczenie %s?" % name,
                               parent=app.root):
        return
    try:
        if entry["kind"] == "filezilla":
            bw_windows_saved.open_filezilla_site(entry["entry"])
        else:
            p = entry["profile"]
            bw_ssh_direct.connect_interactive(p["host"], p["user"], p["port"])
        app.mapping_hint.set("Uruchomiono: " + name)
    except (OSError, RuntimeError, ValueError) as exc:
        messagebox.showerror("Nie otwarto polaczenia", str(exc), parent=app.root)
