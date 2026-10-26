"""BeardedWolf command center: dashboard with domain-first status table."""
import tkinter as tk
from tkinter import ttk, messagebox

import bw_fleet
import bw_overview
from bw_theme import COLORS


def _metric(parent, label, variable, color):
    box = tk.Frame(parent, bg=COLORS["panel"], padx=18, pady=12,
                   highlightbackground=COLORS["border"], highlightthickness=1)
    tk.Label(box, text=label, bg=COLORS["panel"], fg=COLORS["muted"],
             font=("DejaVu Sans", 9, "bold")).pack(anchor="w")
    tk.Label(box, textvariable=variable, bg=COLORS["panel"], fg=color,
             font=("DejaVu Sans", 24, "bold")).pack(anchor="w")
    return box


def selected(app):
    items = app.dashboard_table.selection()
    if not items:
        messagebox.showinfo("Wybierz serwis", "Zaznacz domenę w tabeli.",
                            parent=app.root)
        return None
    return app.dashboard_table.set(items[0], "domain")


def site_details(app):
    domain = selected(app)
    if domain:
        app.fleet_search.set("")
        app.fleet_group.set("Wszystkie")
        app.refresh_fleet()
        app.open_site_details(domain)


def website(app):
    domain = selected(app)
    if domain:
        app.open_site_website(domain)


def wordpress(app):
    domain = selected(app)
    if not domain:
        return
    site = bw_fleet.get_site(domain)
    if site.get("type") != "wordpress":
        messagebox.showinfo("Brak WordPressa", "Serwis nie jest oznaczony jako WordPress.",
                            parent=app.root)
        return
    app.open_wp_dialog(domain)


def build(app, tab):
    top = tk.Frame(tab, bg=COLORS["surface"], padx=19, pady=13,
                   highlightbackground=COLORS["border"], highlightthickness=1)
    top.pack(fill="x", pady=(0, 10))
    tk.Label(top, text="BEARDEDWOLF  /  OPERATIONS CENTER",
             bg=COLORS["surface"], fg=COLORS["cyan"],
             font=("DejaVu Sans", 10, "bold")).pack(anchor="w")
    tk.Label(top, text="Monitoring witryn i usług",
             bg=COLORS["surface"], fg=COLORS["fg"],
             font=("DejaVu Sans", 20, "bold")).pack(anchor="w", pady=(4, 1))
    tk.Label(top, text="Techniczna dostępność WWW i ważność TLS. "
             "Nie jest to audyt funkcjonalny ani bezpieczeństwa.",
             bg=COLORS["surface"], fg=COLORS["muted"]).pack(anchor="w")

    bar = ttk.Frame(tab)
    bar.pack(fill="x", pady=(0, 11))
    app.console_stats = []
    for col, (name, color) in enumerate([
        ("DZIAŁAJĄ", COLORS["green"]),
        ("WYMAGAJĄ UWAGI", COLORS["red"]),
        ("NIESPRAWDZONE", COLORS["amber"]),
        ("PRZEKIEROWANIA", COLORS["muted"])
    ]):
        bar.columnconfigure(col, weight=1, uniform="stats")
        var = tk.StringVar(value="0")
        app.console_stats.append(var)
        item = _metric(bar, name, var, color)
        item.grid(row=0, column=col, sticky="nsew",
                  padx=(0, 9) if col < 3 else 0)

    controls = ttk.Frame(tab)
    controls.pack(fill="x", pady=(0, 9))
    ttk.Label(controls, text="Filtr domen:").pack(side="left", padx=(0, 5))
    search = ttk.Entry(controls, textvariable=app.dashboard_search, width=31)
    search.pack(side="left", padx=(0, 12))
    app.dashboard_search.trace_add("write", lambda *_: draw(app))
    app.dashboard_group_combo = ttk.Combobox(
        controls, textvariable=app.dashboard_filter,
        values=("Wszystkie",), state="readonly", width=16
    )
    app.dashboard_group_combo.pack(side="left", padx=(0, 8))
    app.dashboard_group_combo.bind("<<ComboboxSelected>>",
                                   lambda _evt: draw(app))
    ttk.Button(controls, text="Sprawdź WWW i TLS", style="Accent.TButton",
               command=app.refresh_dashboard).pack(side="right")
    ttk.Button(controls, text="Sprawdź WordPress",
               command=app.refresh_wp_batch).pack(side="right", padx=(0, 9))

    app.dashboard_hint = tk.StringVar(value="Oczekiwanie na pomiar serwisów.")
    ttk.Label(tab, textvariable=app.dashboard_hint).pack(
        anchor="w", fill="x", pady=(0, 7))

    holder = ttk.Frame(tab)
    holder.pack(fill="both", expand=True)
    cols = ("domain", "status", "http", "tls", "latency", "group", "type")
    tree = ttk.Treeview(holder, columns=cols, show="headings", selectmode="browse")
    app.dashboard_table = tree
    for key, name, width in [
        ("domain", "DOMENA / SERWIS", 270),
        ("status", "STAN TECHNICZNY", 205),
        ("http", "HTTP", 70),
        ("tls", "CERTYFIKAT", 150),
        ("latency", "ODPOWIEDŹ", 105),
        ("group", "GRUPA", 105),
        ("type", "TYP", 135)
    ]:
        tree.heading(key, text=name)
        tree.column(key, width=width, stretch=(key == "domain"))
    for tag, color in [
        ("healthy", COLORS["green"]),
        ("warning", COLORS["amber"]),
        ("critical", COLORS["red"]),
        ("redirect", COLORS["muted"]),
        ("unknown", COLORS["muted"])
    ]:
        tree.tag_configure(tag, foreground=color)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    scrollbar.pack(side="right", fill="y")
    tree.configure(yscrollcommand=scrollbar.set)
    tree.bind("<Double-1>", lambda _evt: site_details(app))

    actions = ttk.Frame(tab)
    actions.pack(fill="x", pady=(9, 0))
    ttk.Button(actions, text="Szczegóły serwisu",
               command=lambda: site_details(app)).pack(side="left", padx=(0, 8))
    ttk.Button(actions, text="Otwórz WWW",
               command=lambda: website(app)).pack(side="left", padx=(0, 8))
    ttk.Button(actions, text="Aktualizacje WP",
               command=lambda: wordpress(app)).pack(side="left")
    ttk.Label(actions, text="Problemy pierwsze, przekierowania ostatnie.",
              foreground=COLORS["muted"]).pack(side="right")
    draw(app)


def draw(app):
    """Redraw 22-100 records cheaply; preserve selection and show redirects last."""
    if not hasattr(app, "dashboard_table"):
        return
    tree = app.dashboard_table
    selection = tree.selection()
    prior = tree.set(selection[0], "domain") if selection else None
    try:
        sites = bw_fleet.inventory()["sites"]
    except (OSError, ValueError, RuntimeError) as exc:
        app.dashboard_hint.set("Nie można odczytać rejestru: " + str(exc))
        return
    groups = ["Wszystkie"] + sorted({s.get("group", "inne") for s in sites})
    app.dashboard_group_combo.configure(values=groups)
    if app.dashboard_filter.get() not in groups:
        app.dashboard_filter.set("Wszystkie")
    term = app.dashboard_search.get().strip().casefold()
    selected_group = app.dashboard_filter.get()
    shown = [s for s in sites if
             (selected_group == "Wszystkie" or s.get("group") == selected_group)
             and (not term or term in s["domain"].casefold())]
    shown.sort(key=lambda s: bw_overview.order(
        s, app.dashboard_results.get(s["domain"])))
    for item in tree.get_children():
        tree.delete(item)
    for site in shown:
        domain = site["domain"]
        label, severity, code, tls, latency = bw_overview.presentation(
            site, app.dashboard_results.get(domain)
        )
        tree.insert("", "end", iid=domain, tags=(severity,), values=(
            domain, label, code, tls, latency,
            site.get("group", ""), site.get("type", "")
        ))
    if prior and tree.exists(prior):
        tree.selection_set(prior)
        tree.see(prior)
    totals = bw_overview.metrics(sites, app.dashboard_results)
    for widget, count in zip(
        app.console_stats,
        (totals["healthy"], totals["alerts"], totals["unchecked"], totals["redirects"])
    ):
        widget.set(str(count))


def paint(app, domain):
    """Single call site for old pump; ordering always follows newest measurements."""
    draw(app)
