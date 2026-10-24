#!/usr/bin/env python3
"""BeardedWolf Admin: graficzny panel diagnostyki i połączeń SSH (Kali XFCE)."""
import importlib.util
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib.machinery import SourceFileLoader
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import bw_servers
import bw_fleet
import bw_filezilla
import bw_monitor
import bw_wp

HERE = Path(__file__).resolve().parent
CLI_FILE = HERE / "bw"
loader = SourceFileLoader("bw_cli", str(CLI_FILE))
spec = importlib.util.spec_from_loader("bw_cli", loader)
bw_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bw_cli)


class AdminApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BeardedWolf Admin | Centrum diagnostyki")
        self.root.geometry("1100x770")
        self.root.minsize(880, 630)
        self.messages = queue.Queue()
        self.last_report = None
        self.profiles = []
        self.managed_sites = []
        self.dashboard_results = {}
        self.dashboard_cards = {}
        self.dashboard_running = False
        self.wp_cache = {}
        self.wp_errors = {}
        self.wp_dialogs = {}
        self.wp_batch_running = False
        self.fleet_running = False
        self.last_fleet_report = None
        self.table_sort = {}
        self.table_headings = {}
        self.editing_alias = None
        self.running = False

        self.domain = tk.StringVar(value="")
        self.do_dns = tk.BooleanVar(value=True)
        self.do_tls = tk.BooleanVar(value=True)
        self.do_http = tk.BooleanVar(value=True)
        self.export = tk.BooleanVar(value=False)
        self.alias = tk.StringVar()
        self.host = tk.StringVar()
        self.username = tk.StringVar()
        self.port = tk.StringVar(value="22")
        self.status = tk.StringVar(value="Gotowy do pracy. Wybierz test lub serwer.")
        self.dashboard_filter = tk.StringVar(value="Wszystkie")

        self.build()
        self.refresh_servers()
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)
        self.root.after(120, self.pump)
        self.root.after(900, self.refresh_dashboard)
        self.root.after(15 * 60 * 1000, self.periodic_dashboard)

    def on_app_close(self):
        if any(dialog.get("busy") for dialog in self.wp_dialogs.values()):
            messagebox.showwarning(
                "Trwa operacja WordPress",
                "Sprawdzanie lub aktualizacja WordPress jeszcze trwa. "
                "Zakończ operację przed zamknięciem aplikacji.",
                parent=self.root
            )
            return
        self.root.destroy()

    def build(self):
        frame = ttk.Frame(self.root, padding=14)
        frame.pack(fill="both", expand=True)

        title = ttk.Label(frame, text="BeardedWolf Admin", font=("Sans", 19, "bold"))
        title.pack(anchor="w")
        ttk.Label(frame, text="Audyt pasywny domen i szybkie połączenia z serwerami",
                  font=("Sans", 10)).pack(anchor="w", pady=(0, 12))

        tabs = ttk.Notebook(frame)
        tabs.pack(fill="both", expand=True)
        dashboard = ttk.Frame(tabs, padding=14)
        tests = ttk.Frame(tabs, padding=14)
        servers = ttk.Frame(tabs, padding=14)
        fleet = ttk.Frame(tabs, padding=14)
        controls = ttk.Frame(tabs, padding=14)
        reports = ttk.Frame(tabs, padding=14)
        tabs.add(dashboard, text="  Pulpit  ")
        tabs.add(fleet, text="  Wszystkie serwisy  ")
        tabs.add(tests, text="  Testy domen  ")
        tabs.add(servers, text="  Serwery SSH  ")
        tabs.add(controls, text="  Kontrole T01–T40  ")
        tabs.add(reports, text="  Raporty i informacje  ")
        self.tabs = tabs
        self.fleet_tab = fleet
        self.build_dashboard(dashboard)
        self.build_fleet(fleet)
        self.build_controls(controls)
        self.build_tests(tests)
        self.build_servers(servers)
        self.build_reports(reports)

        ttk.Separator(frame).pack(fill="x", pady=(10, 8))
        ttk.Label(frame, textvariable=self.status, wraplength=820).pack(
            anchor="w", fill="x")

    def build_dashboard(self, tab):
        header = ttk.Frame(tab)
        header.pack(fill="x", pady=(0, 9))
        ttk.Label(header, text="Stan zarządzanych serwisów",
                  font=("Sans", 14, "bold")).pack(side="left")
        ttk.Button(header, text="Odśwież stan WWW i TLS",
                   command=self.refresh_dashboard).pack(side="right", padx=(7, 0))
        ttk.Button(header, text="Sprawdź aktualizacje WP",
                   command=self.refresh_wp_batch).pack(side="right", padx=(7, 0))
        groups = ["Wszystkie"] + sorted({s.get("group", "inne")
                                        for s in bw_fleet.inventory()["sites"]})
        combo = ttk.Combobox(header, textvariable=self.dashboard_filter,
                             values=groups, width=15, state="readonly")
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", lambda _event: self.draw_dashboard())
        ttk.Label(header, text="Grupa:").pack(side="right", padx=(6, 4))
        self.dashboard_hint = tk.StringVar(
            value="Wyniki na żywo tylko dla serwisów z zatwierdzonym zakresem. "
                  "Aktualizacje WordPress wymagają osobnego sprawdzenia przez SSH.")
        ttk.Label(tab, textvariable=self.dashboard_hint, wraplength=850).pack(
            anchor="w", fill="x", pady=(0, 8))
        content = ttk.Frame(tab)
        content.pack(fill="both", expand=True)
        self.dashboard_canvas = tk.Canvas(content, highlightthickness=0, borderwidth=0)
        scroll = ttk.Scrollbar(content, orient="vertical",
                               command=self.dashboard_canvas.yview)
        self.dashboard_canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.dashboard_canvas.pack(side="left", fill="both", expand=True)
        self.dashboard_inner = ttk.Frame(self.dashboard_canvas)
        self.dashboard_window = self.dashboard_canvas.create_window(
            (0, 0), window=self.dashboard_inner, anchor="nw"
        )
        self.dashboard_inner.bind(
            "<Configure>",
            lambda _event: self.dashboard_canvas.configure(
                scrollregion=self.dashboard_canvas.bbox("all")
            )
        )
        self.dashboard_canvas.bind("<Configure>", self.resize_dashboard)
        self.draw_dashboard()

    def resize_dashboard(self, event):
        self.dashboard_canvas.itemconfigure(self.dashboard_window, width=event.width)
        cols = 3 if event.width >= 1120 else (2 if event.width >= 650 else 1)
        if getattr(self, "dashboard_columns", None) != cols:
            self.dashboard_columns = cols
            self.draw_dashboard()

    def draw_dashboard(self):
        for widget in self.dashboard_inner.winfo_children():
            widget.destroy()
        self.dashboard_cards = {}
        sites = bw_fleet.inventory()["sites"]
        filter_name = self.dashboard_filter.get()
        if filter_name != "Wszystkie":
            sites = [s for s in sites if s.get("group") == filter_name]
        cols = getattr(self, "dashboard_columns", 2)
        for col in range(cols):
            self.dashboard_inner.columnconfigure(col, weight=1, uniform="cards")
        for idx, site in enumerate(sites):
            domain = site["domain"]
            card = ttk.LabelFrame(self.dashboard_inner, text=domain, padding=11)
            card.grid(row=idx // cols, column=idx % cols, sticky="nsew", padx=5, pady=5)
            status = ttk.Label(card, font=("Sans", 11, "bold"))
            status.pack(anchor="w", pady=(0, 5))
            http = ttk.Label(card)
            http.pack(anchor="w", pady=2)
            tls = ttk.Label(card)
            tls.pack(anchor="w", pady=2)
            checked = ttk.Label(card)
            checked.pack(anchor="w", pady=2)
            wp = ttk.Label(card)
            wp.pack(anchor="w", pady=(2, 7))
            ttk.Label(
                card, text=site.get("group", "") + " | " +
                ("platforma nieustalona" if site.get("type") == "sprawdzic"
                 else site.get("type", "")), wraplength=360
            ).pack(anchor="w")
            buttons = ttk.Frame(card)
            buttons.pack(anchor="w", pady=(8, 0))
            ttk.Button(buttons, text="Szczegóły",
                       command=lambda d=domain: self.open_site_details(d)).pack(
                side="left", padx=(0, 5))
            ttk.Button(buttons, text="Otwórz WWW",
                       command=lambda d=domain: self.open_site_website(d)).pack(
                side="left", padx=(0, 5))
            if site.get("type") == "wordpress":
                ttk.Button(
                    buttons, text="Aktualizacje WP",
                    command=lambda d=domain: self.open_wp_dialog(d)
                ).pack(side="left")
            self.dashboard_cards[domain] = (status, http, tls, checked, wp, site)
            self.paint_dashboard_card(domain)

    def paint_dashboard_card(self, domain):
        controls = self.dashboard_cards.get(domain)
        if not controls:
            return
        status, http, tls, checked, wp, site = controls
        data = self.dashboard_results.get(domain)
        if not site.get("authorized"):
            status.configure(text="○ Niepotwierdzony zakres")
            http.configure(text="WWW: nie sprawdzono")
            tls.configure(text="TLS: nie sprawdzono")
            checked.configure(text="Ostatni pomiar: brak")
        elif data is None:
            status.configure(text="○ Oczekuje na kontrolę")
            http.configure(text="WWW: nie sprawdzono")
            tls.configure(text="TLS: nie sprawdzono")
            checked.configure(text="Ostatni pomiar: brak")
        else:
            status.configure(text=bw_monitor.display_status(data))
            http.configure(
                text="HTTP: " + str(data["http"] if data.get("http") is not None else "błąd") +
                "  |  " + (str(data["response_ms"]) + " ms"
                           if data.get("response_ms") is not None else "czas nieznany")
            )
            extra = (" (do " + data["tls_expires"] + ", " +
                     str(data["tls_days"]) + " dni)" if data.get("tls_expires") else "")
            tls.configure(text="TLS: " + data.get("tls", "brak") + extra)
            checked.configure(text="Sprawdzono UTC: " + data.get("checked_at", "")[:19])
        if site.get("type") == "wordpress":
            recent = self.wp_cache.get(domain)
            if recent:
                wp.configure(
                    text=f"WP: Core {'aktualizacja' if recent['core_update'] else 'OK'}"
                         f"  |  wtyczki do aktualizacji: {recent['plugin_count']}"
                )
            elif domain in self.wp_errors:
                wp.configure(text="WP: BŁĄD SPRAWDZENIA SSH/WP-CLI")
            else:
                wp.configure(text="WP: aktualizacje nie sprawdzone przez SSH")
        else:
            wp.configure(text="WordPress: nie dotyczy lub nie rozpoznano")

    def periodic_dashboard(self):
        # Pomiar cykliczny tylko wtedy, gdy pulpit Kali i aplikacja nadal działają.
        self.refresh_dashboard()
        self.root.after(15 * 60 * 1000, self.periodic_dashboard)

    def refresh_dashboard(self):
        if self.dashboard_running:
            return
        sites = [s for s in bw_fleet.inventory()["sites"] if s.get("authorized")
                 and s.get("public_checks")]
        if not sites:
            self.dashboard_hint.set(
                "Brak serwisów zatwierdzonych do testów publicznych. "
                "Potwierdź zakres w zakładce Wszystkie serwisy."
            )
            return
        self.dashboard_running = True
        self.dashboard_hint.set(f"Sprawdzam WWW i TLS dla {len(sites)} serwisów...")
        threading.Thread(target=self.dashboard_worker, args=(sites,), daemon=True).start()

    def dashboard_worker(self, sites):
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(bw_monitor.check, s["domain"]): s["domain"]
                       for s in sites}
            for future in as_completed(futures):
                domain = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"domain": domain, "status": "BŁĄD POMIARU",
                              "tls": "NIE SPRAWDZONO", "http": None,
                              "checked_at": "", "error": str(exc)[:150]}
                self.messages.put(("dashboard_site", domain, result))
        self.messages.put(("dashboard_finished", len(sites)))

    def open_site_website(self, domain):
        verified = bw_fleet.base.domain_name(domain)
        try:
            subprocess.Popen(
                ["xdg-open", "https://" + verified + "/"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except OSError as exc:
            messagebox.showerror("Nie otwarto strony", str(exc), parent=self.root)

    def refresh_wp_batch(self):
        if self.wp_batch_running:
            return
        eligible = []
        for site in bw_fleet.inventory()["sites"]:
            if (site.get("type") == "wordpress" and site.get("authorized") and
                    site.get("ssh_alias") and site.get("wp_root")):
                eligible.append(site)
        if not eligible:
            messagebox.showinfo(
                "Brak skonfigurowanych WordPressów",
                "Do zbiorczego sprawdzania wymagane są: platforma WordPress, "
                "potwierdzony zakres, profil SSH z kluczem i zweryfikowana ścieżka WWW. "
                "Przypisz te dane w zakładce Wszystkie serwisy.",
                parent=self.root
            )
            return
        if not messagebox.askyesno(
            "Zbiorcza kontrola WordPress",
            f"Sprawdzić aktualizacje Core i wtyczek na {len(eligible)} "
            "skonfigurowanych serwisach przez SSH? "
            "WP-CLI może odświeżyć metadane aktualizacji w bazie, "
            "ale niczego nie zainstaluje. "
            "Sprawdzanie będzie sekwencyjne, by nie przeciążać hostingu.",
            parent=self.root
        ):
            return
        self.wp_batch_running = True
        self.dashboard_hint.set(
            f"Sprawdzam aktualizacje WordPress na {len(eligible)} stronach...")
        threading.Thread(target=self.wp_batch_worker, args=(eligible,), daemon=True).start()

    def wp_batch_worker(self, sites):
        for site in sites:
            try:
                report = bw_wp.list_updates(site)
                self.messages.put(("wp_batch_site", site["domain"], report, None))
            except Exception as exc:
                self.messages.put(("wp_batch_site", site["domain"], None, str(exc)))
        self.messages.put(("wp_batch_finished", len(sites)))

    def open_site_details(self, domain):
        for iid in self.site_list.get_children():
            if self.site_list.set(iid, "domain") == domain:
                self.site_list.selection_set(iid)
                self.site_list.focus(iid)
                self.site_list.see(iid)
                self.tabs.select(self.fleet_tab)
                self.status.set("Wybrano serwis: " + domain)
                return

    def open_wp_dialog(self, domain):
        existing = self.wp_dialogs.get(domain)
        if existing and existing["window"].winfo_exists():
            existing["window"].lift()
            return
        site = bw_fleet.get_site(domain)
        dialog = tk.Toplevel(self.root)
        dialog.title("WordPress: aktualizacje | " + domain)
        dialog.geometry("930x600")
        dialog.minsize(750, 490)
        dialog.transient(self.root)
        controls = ttk.Frame(dialog, padding=15)
        controls.pack(fill="both", expand=True)
        ttk.Label(controls, text="Aktualizacje WordPress: " + domain,
                  font=("Sans", 13, "bold")).pack(anchor="w", pady=(0, 7))
        route = ("Profil SSH: " + str(site.get("ssh_alias") or "BRAK") +
                 "   |   Katalog: " + str(site.get("wp_root") or "BRAK"))
        ttk.Label(controls, text=route, wraplength=880).pack(anchor="w")
        ttk.Label(controls,
                  text="Sprawdzenie: tylko odczyt WP-CLI przez SSH. Aktualizacje wymagają "
                       "osobnego potwierdzenia, działającego backupu plików i bazy. "
                       "Narzędzie nie tworzy automatycznie kopii i nie przywraca strony. Przy aktualizacji Core wykonywana jest też migracja bazy WordPress.",
                  wraplength=880).pack(anchor="w", pady=(7, 9))
        details = tk.StringVar(value="Core: nie sprawdzono")
        ttk.Label(controls, textvariable=details,
                  font=("Sans", 11, "bold")).pack(anchor="w", pady=(3, 6))
        wrapper = ttk.Frame(controls)
        wrapper.pack(fill="both", expand=True)
        tree = ttk.Treeview(wrapper, show="headings", selectmode="extended",
                            columns=("name", "version", "target", "state"))
        for col, label, width in [
            ("name", "Wtyczka", 300), ("version", "Aktualna", 115),
            ("target", "Dostępna", 115), ("state", "Status", 160)
        ]:
            tree.heading(col, text=label)
            tree.column(col, width=width, stretch=col == "name")
        tree.pack(side="left", fill="both", expand=True)
        vscroll = ttk.Scrollbar(wrapper, command=tree.yview, orient="vertical")
        vscroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=vscroll.set)
        row = ttk.Frame(controls)
        row.pack(fill="x", pady=(11, 5))
        check_btn = ttk.Button(row, text="Sprawdź aktualizacje",
                               command=lambda: self.check_wp_updates(domain))
        check_btn.pack(side="left", padx=(0, 8))
        plugin_btn = ttk.Button(
            row, text="Aktualizuj zaznaczone wtyczki",
            command=lambda: self.confirm_wp_action(domain, "plugins")
        )
        plugin_btn.pack(side="left", padx=(0, 8))
        core_btn = ttk.Button(
            row, text="Aktualizuj WordPress Core",
            command=lambda: self.confirm_wp_action(domain, "core")
        )
        core_btn.pack(side="left")
        state = tk.StringVar(value="Gotowe do sprawdzenia.")
        ttk.Label(controls, textvariable=state, wraplength=880).pack(
            fill="x", anchor="w", pady=(5, 0))
        self.wp_dialogs[domain] = {
            "window": dialog, "status": state, "details": details, "tree": tree,
            "check": check_btn, "plugins": plugin_btn, "core": core_btn,
            "data": None, "busy": False
        }
        plugin_btn.configure(state="disabled")
        core_btn.configure(state="disabled")
        def finish():
            current = self.wp_dialogs.get(domain)
            if current and current["busy"]:
                messagebox.showwarning(
                    "Operacja w toku", "Nie zamykaj okna podczas sprawdzania lub aktualizacji "
                    "na serwerze. Poczekaj na wynik procesu.",
                    parent=dialog
                )
                return
            self.wp_dialogs.pop(domain, None)
            dialog.destroy()
        dialog.protocol("WM_DELETE_WINDOW", finish)
        self.check_wp_updates(domain)

    def wp_set_busy(self, domain, busy):
        record = self.wp_dialogs.get(domain)
        if not record:
            return
        record["busy"] = busy
        record["check"].configure(state="disabled" if busy else "normal")
        has_result = bool(record.get("data"))
        has_plugins = bool(record["data"]["plugin_updates"]) if has_result else False
        has_core = bool(record["data"]["core_targets"]) if has_result else False
        record["plugins"].configure(
            state="normal" if has_plugins and not busy else "disabled"
        )
        record["core"].configure(
            state="normal" if has_core and not busy else "disabled"
        )

    def check_wp_updates(self, domain):
        record = self.wp_dialogs.get(domain)
        if not record or record["busy"]:
            return
        record["status"].set("Sprawdzam przez SSH. Brak zapisu na serwerze...")
        self.wp_set_busy(domain, True)
        threading.Thread(
            target=self.wp_check_worker, args=(domain,), daemon=True
        ).start()

    def wp_check_worker(self, domain):
        try:
            result = bw_wp.list_updates(bw_fleet.get_site(domain))
            self.messages.put(("wp_check_done", domain, result, None))
        except Exception as exc:
            self.messages.put(("wp_check_done", domain, None, str(exc)))

    def confirm_wp_action(self, domain, kind):
        record = self.wp_dialogs.get(domain)
        if not record or record["busy"] or not record.get("data"):
            return
        report = record["data"]
        chosen = []
        if kind == "plugins":
            for item in record["tree"].selection():
                chosen.append(report["plugin_updates"][int(item)])
            if not chosen:
                messagebox.showwarning("Wybierz wtyczki",
                                       "Zaznacz przynajmniej jedną wtyczkę na liście.",
                                       parent=record["window"])
                return
            target = ", ".join(p["name"] + " (" + p["version"] + " → " +
                               p["target"] + ")" for p in chosen)
            label = "Aktualizacja wtyczek: " + target
        else:
            target = sorted(report["core_targets"],
                            key=lambda v: tuple(int(x) for x in v.split(".")))[-1]
            label = ("Aktualizacja WordPress Core: " +
                     report["current_core"] + " → " + target)
        if not messagebox.askyesno(
            "Zmiana produkcyjnej strony WordPress",
            label + "\n\nCzy potwierdzasz, że posiadasz aktualną, odtwarzalną "
            "kopię BAZY DANYCH I PLIKÓW strony oraz możliwość jej przywrócenia? "
            "BeardedWolf Admin NIE tworzy i NIE testuje kopii automatycznie. Przy aktualizacji Core zostanie także wykonane wp core update-db. "
            "Zmiana może spowodować niedostępność serwisu.",
            parent=record["window"]
        ):
            return
        typed = simpledialog.askstring(
            "Ostateczne potwierdzenie aktualizacji",
            "Aby wykonać zmianę na serwerze, wpisz dokładnie domenę:\n" + domain,
            parent=record["window"]
        )
        if typed != domain:
            record["status"].set("Anulowano: nie potwierdzono domeny.")
            return
        self.wp_set_busy(domain, True)
        record["status"].set("Trwa aktualizacja na serwerze " + domain +
                             ". Nie zamykaj panelu do otrzymania wyniku.")
        threading.Thread(
            target=self.wp_update_worker,
            args=(domain, kind, chosen, report, target), daemon=True
        ).start()

    def wp_update_worker(self, domain, kind, chosen, report, target):
        results = []
        try:
            site = bw_fleet.get_site(domain)
            if kind == "plugins":
                for entry in chosen:
                    output = bw_wp.update_plugin(
                        site, entry["name"], entry["version"], entry["target"]
                    )
                    results.append(entry["name"] + ": " + output[-240:])
            else:
                output = bw_wp.update_core(site, report["current_core"], target)
                results.append("Core: " + output[-400:])
            error = None
        except Exception as exc:
            error = str(exc)
        try:
            action = "WordPress Core" if kind == "core" else "Wtyczki WordPress"
            details = "Zakończone operacje: " + str(len(results))
            if error:
                details += ". Błąd: " + error
            bw_wp.record_operation(
                domain, action,
                target if kind == "core" else ", ".join(entry["name"] for entry in chosen),
                not bool(error), details
            )
        except (OSError, ValueError):
            error = (error + ". " if error else "") + "Nie zapisano dziennika aktualizacji."
        self.messages.put(("wp_update_done", domain, kind, results, error))

    def sort_table(self, tree, column):
        """Sortuj widok bez zmiany powiązań identyfikatorów i danych."""
        key = str(tree)
        state = self.table_sort.get(key)
        desc = bool(state and state[0] == column and not state[1])
        self.apply_table_sort(tree, column, desc)

    def apply_table_sort(self, tree, column, descending):
        ids = list(tree.get_children(""))
        def get_value(iid):
            value = str(tree.set(iid, column))
            if column == "port":
                try:
                    return int(value)
                except ValueError:
                    return -1
            if column == "id" and value.startswith("T") and value[1:].isdigit():
                return int(value[1:])
            return value.casefold()
        ordered = sorted(ids, key=get_value, reverse=descending)
        for index, iid in enumerate(ordered):
            tree.move(iid, "", index)
        name = str(tree)
        previous = self.table_sort.get(name)
        if previous:
            original = self.table_headings.get(name, {}).get(previous[0])
            if original:
                tree.heading(previous[0], text=original)
        base_label = self.table_headings.get(name, {}).get(column, column)
        tree.heading(column, text=base_label + (" ↓" if descending else " ↑"))
        self.table_sort[name] = (column, descending)

    def enable_table_sort(self, tree):
        name = str(tree)
        self.table_headings[name] = {}
        for column in tree["columns"]:
            label = tree.heading(column)["text"]
            self.table_headings[name][column] = label
            tree.heading(column, command=lambda col=column, obj=tree: self.sort_table(obj, col))

    def build_fleet(self, tab):
        ttk.Label(tab, text="Zarządzane serwisy i audyty", font=("Sans", 12, "bold")).pack(
            anchor="w", pady=(0, 7))
        ttk.Label(
            tab, text="Rejestr startowy wymaga zatwierdzenia zakresu zarządzania. "
            "Testy publiczne wykonujemy tylko dla potwierdzonych pozycji. "
            "Nie uruchamiamy SSH ani testów plików bez osobnej konfiguracji.",
            wraplength=800, justify="left"
        ).pack(anchor="w", fill="x", pady=(0, 9))
        holder = ttk.Frame(tab)
        holder.pack(fill="both", expand=True)
        self.site_list = ttk.Treeview(holder, show="headings", selectmode="browse",
                                      columns=("domain", "group", "type", "hosting", "access", "host", "ssh", "authorized", "last"), height=11)
        for col, label, width in [
            ("domain", "Domena", 165), ("group", "Grupa", 82),
            ("type", "Platforma", 96), ("hosting", "Hosting", 95),
            ("access", "Dostęp", 95), ("host", "Host dostępowy", 174),
            ("ssh", "SSH profil", 74), ("authorized", "Zakres", 107),
            ("last", "Wynik", 110)
        ]:
            self.site_list.heading(col, text=label)
            self.site_list.column(col, width=width, stretch=col == "domain")
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.site_list.yview)
        self.site_list.configure(yscrollcommand=scrollbar.set)
        self.site_list.pack(side="left", fill="both", expand=True)
        self.enable_table_sort(self.site_list)
        self.site_list.bind("<Double-1>", lambda _evt: self.edit_site())
        scrollbar.pack(side="right", fill="y")
        manage = ttk.Frame(tab)
        manage.pack(anchor="w", fill="x", pady=(8, 0))
        ttk.Button(manage, text="Dodaj serwis", command=self.add_site).pack(side="left", padx=(0, 6))
        ttk.Button(manage, text="Edytuj platformę", command=self.edit_site).pack(side="left", padx=(0, 6))
        ttk.Button(manage, text="Hosting / dostęp", command=self.edit_hosting).pack(side="left", padx=(0, 6))
        ttk.Button(manage, text="Import FileZilla", command=self.import_filezilla).pack(side="left", padx=(0, 6))
        ttk.Button(manage, text="Usuń z rejestru", command=self.remove_site).pack(side="left", padx=(0, 6))
        ssh_row = ttk.Frame(tab)
        ssh_row.pack(anchor="w", fill="x", pady=(5, 0))
        ttk.Button(ssh_row, text="Przypisz SSH / katalog", command=self.map_site_ssh).pack(side="left", padx=(0, 6))
        ttk.Button(ssh_row, text="Utwórz profil SSH", command=self.create_ssh_for_site).pack(side="left", padx=(0, 6))
        ttk.Button(ssh_row, text="Sugerowane powiązania OVH", command=self.apply_known_ssh).pack(
            side="left", padx=(0, 6))
        ttk.Button(ssh_row, text="Połącz z SSH strony", command=self.open_mapped_ssh).pack(side="left")
        line1 = ttk.Frame(tab)
        line1.pack(anchor="w", fill="x", pady=(10, 4))
        ttk.Button(line1, text="Potwierdź zakres", command=self.confirm_site).pack(side="left", padx=(0, 6))
        ttk.Button(line1, text="Wstrzymaj testy", command=self.unconfirm_site).pack(side="left", padx=(0, 6))
        ttk.Button(line1, text="Odśwież listę", command=self.refresh_fleet).pack(side="left")
        line2 = ttk.Frame(tab)
        line2.pack(anchor="w", fill="x", pady=(4, 9))
        self.fleet_scan_button = ttk.Button(line2, text="Test wybranego", command=self.scan_selected_site)
        self.fleet_scan_button.pack(side="left", padx=(0, 6))
        self.fleet_all_button = ttk.Button(line2, text="Sprawdź wszystkie aktywne", command=self.scan_confirmed_sites)
        self.fleet_all_button.pack(side="left", padx=(0, 6))
        ttk.Button(line2, text="Zatwierdź baseline", command=self.approve_selected_baseline).pack(
            side="left", padx=(0, 6))
        ttk.Button(line2, text="Otwórz ostatni raport", command=self.open_fleet_report).pack(side="left")
        ttk.Label(tab, text="Baseline zatwierdza się ręcznie dopiero po sprawdzeniu wyników. "
                  "Bez niego raport pokazuje obserwacje, nie potwierdzony brak zmian.",
                  wraplength=800).pack(anchor="w", fill="x")
        self.refresh_fleet()

    def refresh_fleet(self):
        try:
            self.managed_sites = bw_fleet.inventory()["sites"]
            selected_domain = None
            selected = self.site_list.selection()
            if selected:
                index = int(selected[0])
                if index < len(self.site_list.get_children()):
                    selected_domain = self.site_list.item(selected[0], "values")[0]
            for item in self.site_list.get_children():
                self.site_list.delete(item)
            for index, site in enumerate(self.managed_sites):
                try:
                    last = bw_fleet.latest_report(site["domain"])["state"]
                except (OSError, ValueError, KeyError, TypeError):
                    last = "NIEBADANY"
                hosting = bw_fleet.hosting_info(site)
                access = {"unknown": "nieustalony", "ftp": "FTP (TLS?)",
                          "ssh": "SSH", "ftps": "FTPS", "sftp": "SFTP"}.get(
                              hosting["access"], "nieustalony")
                self.site_list.insert("", "end", iid=str(index), values=(
                    site["domain"], site["group"],
                    "nieustalona" if site["type"] == "sprawdzic" else site["type"],
                    hosting["provider"], access, hosting["host"] or "brak",
                    site.get("ssh_alias") or "BRAK",
                    "POTWIERDZONY" if site.get("authorized") else "DO POTWIERDZENIA",
                    last
                ))
                if site["domain"] == selected_domain:
                    self.site_list.selection_set(str(index))
            sort = self.table_sort.get(str(self.site_list))
            if sort:
                self.apply_table_sort(self.site_list, *sort)
        except Exception as exc:
            messagebox.showerror("Rejestr serwisów", str(exc), parent=self.root)

    def selected_site(self):
        selected = self.site_list.selection()
        if not selected:
            messagebox.showwarning("Wybierz domenę", "Najpierw zaznacz serwis w tabeli.",
                                   parent=self.root)
            return None
        return self.managed_sites[int(selected[0])]

    def add_site(self):
        domain = simpledialog.askstring("Nowy serwis", "Domena (bez https://):",
                                        parent=self.root)
        if not domain:
            return
        group = simpledialog.askstring("Grupa", "Grupa (np. prywatne, jdk, um):",
                                       parent=self.root, initialvalue="prywatne")
        if not group:
            return
        platform = simpledialog.askstring(
            "Platforma", "Typ: wordpress, aplikacja, przekierowanie lub sprawdzic:",
            parent=self.root, initialvalue="sprawdzic"
        )
        if not platform:
            return
        try:
            bw_fleet.add_site(domain.strip().lower(), group, platform.strip().lower())
            self.refresh_fleet()
            self.status.set("Dodano serwis bez autoryzacji testów: " + domain)
        except Exception as exc:
            messagebox.showerror("Nie dodano serwisu", str(exc), parent=self.root)

    def edit_site(self):
        site = self.selected_site()
        if site is None:
            return
        group = simpledialog.askstring(
            "Grupa serwisu " + site["domain"], "Grupa:",
            parent=self.root, initialvalue=site["group"]
        )
        if group is None:
            return
        platform = simpledialog.askstring(
            "Platforma serwisu", "Typ: wordpress, aplikacja, przekierowanie lub sprawdzic:",
            parent=self.root, initialvalue=site["type"]
        )
        if platform is None:
            return
        try:
            bw_fleet.update_site(site["domain"], group, platform.strip().lower())
            self.refresh_fleet()
            self.status.set("Zaktualizowano metadane: " + site["domain"])
        except Exception as exc:
            messagebox.showerror("Nie zaktualizowano", str(exc), parent=self.root)

    def import_filezilla(self):
        """Import one selected host's safe metadata, with explicit confirmation."""
        site = self.selected_site()
        if site is None:
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Wskaż lokalny eksport FileZilli (nie wysyłaj go)",
            filetypes=[("Eksport FileZilla XML", "*.xml"), ("Wszystkie pliki", "*.*")]
        )
        if not path:
            return
        try:
            entries = bw_filezilla.read_export(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Eksport FileZilla", str(exc), parent=self.root)
            return
        if not entries:
            messagebox.showinfo("Eksport FileZilla",
                                "Nie znaleziono poprawnych profili z adresami serwerów.",
                                parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Metadane FileZilla → " + site["domain"])
        dialog.geometry("810x455")
        dialog.minsize(650, 360)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=f"Wybierz połączenie FileZilli dla domeny {site['domain']}. "
                 "Importowane są WYŁĄCZNIE adres, protokół, port i login. "
                 "Żadne hasło nie jest odczytywane ani zapisywane.",
            wraplength=760
        ).pack(anchor="w", fill="x", pady=(0, 12))
        columns = ("name", "host", "access", "user", "port")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        for col, label, width in (
            ("name", "Nazwa FileZilla", 145), ("host", "Host", 230),
            ("access", "Protokół", 95), ("user", "Login", 155),
            ("port", "Port", 55)
        ):
            tree.heading(col, text=label)
            tree.column(col, width=width, stretch=col == "host")
        for index, entry in enumerate(entries):
            tree.insert("", "end", iid=str(index), values=(
                entry["name"], entry["host"], entry["access"], entry["user"], entry["port"]
            ))
        tree.pack(fill="both", expand=True)
        buttons = ttk.Frame(frame)
        buttons.pack(anchor="e", pady=(14, 0))
        def apply_entry():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Wybierz połączenie",
                                       "Zaznacz wpis FileZilli w tabeli.", parent=dialog)
                return
            entry = entries[int(selected[0])]
            if entry["access"] == "unknown":
                messagebox.showwarning(
                    "Nieobsługiwany protokół",
                    "FileZilla używa tu nieznanego lub nieobsługiwanego protokołu. "
                    "Sprawdź go ręcznie; nie przypisujemy w ciemno.",
                    parent=dialog
                )
                return
            current = bw_fleet.hosting_info(site)
            provider = current["provider"]
            if provider == "nieustalony":
                host = entry["host"].lower()
                if host.endswith(".hosting.ovh.net"):
                    provider = "OVHcloud"
                elif host.endswith(".nazwa.pl"):
                    provider = "nazwa.pl"
                # Nie rozpoznawaj dostawcy po samym adresie IP.
            if not messagebox.askyesno(
                "Zatwierdź lokalny import",
                f"Przypisać poniższe metadane do {site['domain']}?\n\n"
                f"Host: {entry['host']}\n"
                f"Protokół: {entry['access']}\n"
                f"Port: {entry['port']}\n"
                f"Login: {entry['user'] or '(brak)'}\n\n"
                f"Zastąpi to dotychczasowy wpis hostingu: "
                f"{current['host'] or '(brak)'}. "
                "Nie zmieni profilu SSH i nie wykona żadnego połączenia. "
                "SFTP samo w sobie nie oznacza dostępu do powłoki.",
                parent=dialog
            ):
                return
            try:
                bw_fleet.update_hosting(
                    site["domain"], provider, entry["access"], entry["host"],
                    entry["port"], entry["user"]
                )
                dialog.destroy()
                self.refresh_fleet()
                self.status.set("Zimportowano metadane FileZilli dla " + site["domain"] +
                                ", bez haseł i połączenia z serwerem.")
            except (OSError, ValueError) as exc:
                messagebox.showerror("Import nieudany", str(exc), parent=dialog)

        ttk.Button(buttons, text="Przypisz do serwisu", command=apply_entry).pack(
            side="left", padx=(0, 8))
        ttk.Button(buttons, text="Anuluj", command=dialog.destroy).pack(side="left")
        dialog.bind("<Escape>", lambda _evt: dialog.destroy())
        dialog.wait_window()

    def edit_hosting(self):
        site = self.selected_site()
        if site is None:
            return
        info = bw_fleet.hosting_info(site)
        dialog = tk.Toplevel(self.root)
        dialog.title("Hosting i dostęp: " + site["domain"])
        dialog.geometry("660x420")
        dialog.minsize(555, 395)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Domena: " + site["domain"],
                  font=("Sans", 11, "bold")).grid(
                      row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        provider = tk.StringVar(value=info["provider"])
        access = tk.StringVar(value=info["access"])
        host = tk.StringVar(value=info["host"] or "")
        port = tk.StringVar(value="" if info["port"] is None else str(info["port"]))
        user = tk.StringVar(value=info["user"] or "")

        ttk.Label(frame, text="Dostawca hostingu:").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Combobox(frame, textvariable=provider, values=(
            "nieustalony", "OVHcloud", "nazwa.pl", "cyber_Folks", "inny"
        )).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Label(frame, text="Potwierdzony protokół:").grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Combobox(frame, textvariable=access, state="readonly",
                     values=("unknown", "ssh", "ftp", "ftps", "sftp")).grid(
            row=2, column=1, sticky="ew", pady=5)
        for row, label, variable in [
            (3, "Adres serwera:", host),
            (4, "Port:", port),
            (5, "Login (bez hasła):", user),
        ]:
            ttk.Label(frame, text=label).grid(
                row=row, column=0, sticky="w", padx=(0, 10), pady=5)
            ttk.Entry(frame, textvariable=variable).grid(
                row=row, column=1, sticky="ew", pady=5)
        ttk.Label(
            frame,
            text="FTP na porcie 21 nie potwierdza SSH ani szyfrowania transferu. "
                 "Nie wpisuj hasła do tego formularza. Jeśli SSH nie jest udostępnione, "
                 "pozostaw profil SSH serwisu nieprzypisany.",
            wraplength=600
        ).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(12, 8))
        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, columnspan=2, sticky="e", pady=(5, 0))

        def save():
            try:
                bw_fleet.update_hosting(
                    site["domain"], provider.get(), access.get(),
                    host.get(), port.get(), user.get()
                )
                dialog.destroy()
                self.refresh_fleet()
                self.status.set("Zaktualizowano hosting: " + site["domain"] +
                                ". Brak zdalnych działań.")
            except (OSError, ValueError) as exc:
                messagebox.showerror("Nie zapisano hostingu", str(exc), parent=dialog)

        ttk.Button(buttons, text="Zapisz", command=save).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Anuluj", command=dialog.destroy).pack(side="left")
        dialog.bind("<Escape>", lambda _evt: dialog.destroy())
        dialog.wait_window()

    def remove_site(self):
        site = self.selected_site()
        if site is None:
            return
        if not messagebox.askyesno(
            "Usuń z rejestru",
            f"Usunąć {site['domain']} z lokalnej inwentaryzacji? "
            "Raporty, baseline i klucze SSH zostaną na dysku. Nie zmieniamy serwera.",
            parent=self.root
        ):
            return
        try:
            bw_fleet.remove_site(site["domain"])
            self.refresh_fleet()
            self.status.set("Usunięto serwis z rejestru: " + site["domain"])
        except Exception as exc:
            messagebox.showerror("Nie usunięto", str(exc), parent=self.root)

    def create_ssh_for_site(self):
        """Create a local SSH profile only from an explicit SSH host and user input."""
        site = self.selected_site()
        if site is None:
            return
        info = bw_fleet.hosting_info(site)
        if info["access"] != "ssh" or not info["host"]:
            messagebox.showwarning(
                "Brak potwierdzonego hosta SSH",
                "Ten serwis nie ma potwierdzonych danych SSH. "
                "FTP nie jest SSH. Sprawdź protokół i adres w danych hostingowych.",
                parent=self.root
            )
            return
        if site.get("ssh_alias"):
            messagebox.showinfo(
                "Profil już przypisany",
                "Serwis ma już profil " + site["ssh_alias"] +
                ". Możesz go zmienić przyciskiem Przypisz SSH / katalog.",
                parent=self.root
            )
            return
        suggested = "pttk" if site["domain"] == "jaslopttk.pl" else site["domain"].split(".")[0]
        alias = simpledialog.askstring(
            "Nowy lokalny profil SSH",
            f"Alias dla {site['domain']} ({info['host']}):",
            parent=self.root, initialvalue=suggested
        )
        if not alias:
            return
        user = simpledialog.askstring(
            "Login konta SSH",
            "Wpisz potwierdzony login SSH (nie hasło). Bez loginu nie tworzymy profilu.",
            parent=self.root, initialvalue=info["user"] or ""
        )
        if not user:
            return
        if not messagebox.askyesno(
            "Zapisz lokalny profil SSH",
            f"Serwis: {site['domain']}\n"
            f"Profil: {alias}\n"
            f"Połączenie: {user}@{info['host']}:{info['port'] or 22}\n\n"
            "Zapis dotyczy wyłącznie plików konfiguracji lokalnej. "
            "Nie wykonujemy logowania, nie wysyłamy klucza i nie zmieniamy serwera.",
            parent=self.root
        ):
            return
        try:
            bw_servers.add_profile(alias.strip(), info["host"], user.strip(), info["port"] or 22)
            bw_fleet.assign_ssh(site["domain"], alias.strip(), site.get("wp_root"))
            self.refresh_servers()
            self.refresh_fleet()
            self.status.set("Dodano profil SSH dla " + site["domain"] +
                            ". Skonfiguruj klucz w zakładce Serwery SSH.")
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror(
                "Nie ukończono konfiguracji",
                str(exc) + "\nJeśli zapis profilu SSH się udał, ale przypisanie "
                "do serwisu nie, sprawdź oba wpisy przed ponowną próbą.",
                parent=self.root
            )

    def map_site_ssh(self):
        site = self.selected_site()
        if site is None:
            return
        try:
            available = bw_servers.load_profiles()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Profile SSH", str(exc), parent=self.root)
            return
        aliases = ["(brak)"] + sorted(p["alias"] for p in available)
        current = site.get("ssh_alias")
        if current and current not in aliases:
            aliases.append(current)
        dialog = tk.Toplevel(self.root)
        dialog.title("Połącz serwis z SSH: " + site["domain"])
        dialog.geometry("615x295")
        dialog.resizable(True, False)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Domena: " + site["domain"],
                  font=("Sans", 11, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(frame, text="Zapisany profil SSH na tym komputerze:").pack(anchor="w")
        selected = tk.StringVar(value=current or "(brak)")
        combo = ttk.Combobox(frame, textvariable=selected, values=aliases, state="readonly")
        combo.pack(fill="x", pady=(3, 12))
        ttk.Label(frame, text="Katalog WordPress na serwerze (opcjonalny):").pack(anchor="w")
        root_var = tk.StringVar(value=site.get("wp_root") or "")
        ttk.Entry(frame, textvariable=root_var).pack(fill="x", pady=(3, 8))
        ttk.Label(frame, text="Przykład: /home/jaslo/beardedwolf. Katalog musi zostać "
                  "zweryfikowany na właściwym serwerze. Sam zapis nie uruchamia SSH.",
                  wraplength=565).pack(anchor="w")
        buttons = ttk.Frame(frame)
        buttons.pack(anchor="e", pady=(16, 0))
        def save():
            chosen = selected.get()
            try:
                bw_fleet.assign_ssh(
                    site["domain"], None if chosen == "(brak)" else chosen,
                    root_var.get()
                )
                dialog.destroy()
                self.refresh_fleet()
                self.status.set(f"Przypisano SSH do {site['domain']}: "
                                f"{chosen}. Nie wykonywano połączenia.")
            except (OSError, RuntimeError, ValueError) as exc:
                messagebox.showerror("Nie zapisano powiązania", str(exc), parent=dialog)
        ttk.Button(buttons, text="Zapisz powiązanie", command=save).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Anuluj", command=dialog.destroy).pack(side="left")
        dialog.bind("<Escape>", lambda _evt: dialog.destroy())
        combo.focus_set()
        dialog.wait_window()

    def apply_known_ssh(self):
        try:
            preview = bw_fleet.suggestion_preview()
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("Sugerowane powiązania", str(exc), parent=self.root)
            return
        if not preview:
            messagebox.showinfo(
                "Brak nowych podpowiedzi",
                "Brak nieprzypisanych serwisów z potwierdzonym profilem SSH. "
                "Sprawdź, czy istnieją profile jaslo i jdk.",
                parent=self.root
            )
            return
        details = "\n".join(f"• {domain} → {alias}" for domain, alias in preview)
        if not messagebox.askyesno(
            "Zastosować powiązania OVH?",
            "Przypisać wskazane profile do serwisów?\n\n" + details +
            "\n\nIstniejące powiązania zostaną zachowane, a katalogi instalacji "
            "pozostaną puste. Nie zostanie wykonane żadne SSH ani skan.",
            parent=self.root
        ):
            return
        try:
            applied = bw_fleet.apply_suggestions()
            self.refresh_fleet()
            self.status.set(f"Zapisano {len(applied)} sugerowanych powiązań SSH.")
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("Błąd przypisywania SSH", str(exc), parent=self.root)

    def open_mapped_ssh(self):
        site = self.selected_site()
        if site is None:
            return
        alias = site.get("ssh_alias")
        if not alias:
            messagebox.showwarning("Brak powiązania", "Przypisz najpierw profil SSH do serwisu.",
                                   parent=self.root)
            return
        profiles = {p["alias"]: p for p in bw_servers.load_profiles()}
        profile = profiles.get(alias)
        if profile is None:
            messagebox.showerror("Nieaktywny alias SSH",
                                 f"Nie znaleziono profilu {alias}. Popraw powiązanie.",
                                 parent=self.root)
            return
        if not messagebox.askyesno(
            "Połączenie SSH",
            f"Otworzyć sesję do profilu {alias} ({profile['user']}@{profile['host']})? "
            "Samo połączenie nie uruchamia testów hostowych.",
            parent=self.root
        ):
            return
        try:
            bw_servers.connect(profile)
            self.status.set("Otwieram SSH: " + alias + " dla " + site["domain"])
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("Nie udało się połączyć", str(exc), parent=self.root)

    def confirm_site(self):
        site = self.selected_site()
        if site is None:
            return
        if not messagebox.askyesno(
            "Potwierdzenie zakresu zarządzania",
            f"Potwierdzasz uprawnienie do pasywnych kontroli publicznych domeny "
            f"{site['domain']}? Operacja nie uruchomi jeszcze skanowania.",
            parent=self.root
        ):
            return
        try:
            bw_fleet.set_authorized(site["domain"], True)
            self.refresh_fleet()
            self.status.set("Potwierdzono zakres testów: " + site["domain"])
        except Exception as exc:
            messagebox.showerror("Nie zapisano", str(exc), parent=self.root)

    def unconfirm_site(self):
        site = self.selected_site()
        if site is None:
            return
        if not messagebox.askyesno(
            "Wstrzymaj testowanie",
            f"Wstrzymać nowe testy dla {site['domain']}? Raporty i baseline pozostaną lokalnie.",
            parent=self.root
        ):
            return
        try:
            bw_fleet.set_authorized(site["domain"], False)
            self.refresh_fleet()
            self.status.set("Wstrzymano testy: " + site["domain"])
        except Exception as exc:
            messagebox.showerror("Nie zapisano", str(exc), parent=self.root)

    def scan_selected_site(self):
        site = self.selected_site()
        if site is not None:
            self.start_fleet_scan([site])

    def scan_confirmed_sites(self):
        sites = [s for s in self.managed_sites
                 if s.get("authorized") and s.get("public_checks")]
        if not sites:
            messagebox.showinfo("Brak aktywnych serwisów",
                                "Najpierw potwierdź zakres dla odpowiednich domen.",
                                parent=self.root)
            return
        if not messagebox.askyesno(
            "Kontrola wielu serwisów",
            f"Uruchomić pasywne kontrole {len(sites)} potwierdzonych serwisów? "
            "Raporty zostaną zapisane wyłącznie lokalnie.",
            parent=self.root
        ):
            return
        self.start_fleet_scan(sites)

    def start_fleet_scan(self, sites):
        if self.fleet_running:
            return
        if any(not s.get("authorized") for s in sites):
            messagebox.showwarning("Brak potwierdzenia",
                                   "Najpierw potwierdź zakres zarządzania tym serwisem.",
                                   parent=self.root)
            return
        self.fleet_running = True
        self.fleet_scan_button.configure(state="disabled")
        self.fleet_all_button.configure(state="disabled")
        self.status.set(f"Sprawdzanie serwisów: {len(sites)}")
        threading.Thread(target=self.fleet_worker, args=(list(sites),), daemon=True).start()

    def fleet_worker(self, sites):
        results = []
        for site in sites:
            try:
                result, (_, html) = bw_fleet.public_probe(site)
                results.append((site["domain"], result["state"], str(html)))
            except Exception as exc:
                results.append((site["domain"], "BŁĄD", str(exc)))
        self.messages.put(("fleet_done", results))

    def approve_selected_baseline(self):
        site = self.selected_site()
        if site is None:
            return
        if not messagebox.askyesno(
            "Zatwierdzenie stanu referencyjnego",
            f"Czy zweryfikowałeś ostatni raport dla {site['domain']} i świadomie "
            "uznajesz jego udane pomiary za stan referencyjny? "
            "Aktualna konfiguracja zostanie użyta do późniejszych porównań.",
            parent=self.root
        ):
            return
        try:
            path = bw_fleet.approve_baseline(site["domain"])
            self.status.set("Zatwierdzono baseline: " + str(path))
        except Exception as exc:
            messagebox.showerror("Nie zatwierdzono baseline", str(exc), parent=self.root)

    def open_fleet_report(self):
        site = self.selected_site()
        if site is None:
            return
        directory = bw_fleet.site_report_dir(site["domain"])
        reports = sorted(directory.glob("audit_*.html"), reverse=True)
        if not reports:
            messagebox.showinfo("Brak raportów", "Nie ma jeszcze raportu tej domeny.",
                                parent=self.root)
            return
        self.open_path(reports[0])

    def build_tests(self, tab):
        ttk.Label(tab, text="Domena do sprawdzenia:", font=("Sans", 11, "bold")).pack(anchor="w")
        entry = ttk.Entry(tab, textvariable=self.domain, width=48)
        entry.pack(fill="x", pady=(5, 14))
        entry.bind("<Return>", lambda _event: self.run_tests())

        block = ttk.LabelFrame(tab, text="Zakres sprawdzenia", padding=12)
        block.pack(fill="x")
        ttk.Checkbutton(block, text="DNS: rekordy A, AAAA, MX, NS, SPF, DMARC",
                        variable=self.do_dns).pack(anchor="w", pady=3)
        ttk.Checkbutton(block, text="TLS: certyfikat, ważność, protokół, szyfr",
                        variable=self.do_tls).pack(anchor="w", pady=3)
        ttk.Checkbutton(block, text="WWW: odpowiedź HTTPS i nagłówki bezpieczeństwa",
                        variable=self.do_http).pack(anchor="w", pady=3)

        ttk.Checkbutton(tab, text="Zapisz raport także w Syncthing (świadomy eksport na drugi komputer)",
                        variable=self.export).pack(anchor="w", pady=(14, 4))
        ttk.Label(tab, text="Domyślnie raport jest tylko lokalny. Nie synchronizuj danych poufnych.",
                  wraplength=750).pack(anchor="w", pady=(0, 12))

        buttons = ttk.Frame(tab)
        buttons.pack(anchor="w", fill="x", pady=(0, 10))
        self.start_button = ttk.Button(buttons, text="Uruchom wybrane testy", command=self.run_tests)
        self.start_button.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Otwórz ostatni raport",
                   command=self.open_last).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Folder raportów",
                   command=self.open_reports).pack(side="left")

        ttk.Label(tab, text="Przebieg operacji:", font=("Sans", 10, "bold")).pack(anchor="w")
        output = ttk.Frame(tab)
        output.pack(fill="both", expand=True, pady=(5, 0))
        self.log = tk.Text(output, height=10, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(output, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.append_log("Wpisz domenę i wybierz testy. Żaden test nie uruchamia się automatycznie.")

    def build_servers(self, tab):
        ttk.Label(tab, text="Zapisane serwery (lokalnie, bez haseł):",
                  font=("Sans", 11, "bold")).pack(anchor="w")
        block = ttk.Frame(tab)
        block.pack(fill="x", pady=(6, 12))
        self.server_list = ttk.Treeview(block, columns=("alias", "host", "user", "port"),
                                        show="headings", height=6, selectmode="browse")
        for col, name, width in (("alias", "Alias", 130), ("host", "Host", 285),
                                 ("user", "Użytkownik", 140), ("port", "Port", 65)):
            self.server_list.heading(col, text=name)
            self.server_list.column(col, width=width, stretch=col == "host")
        self.server_list.pack(fill="x")
        self.enable_table_sort(self.server_list)
        self.server_list.bind("<<TreeviewSelect>>", self.on_server_select)

        fields = ttk.LabelFrame(tab, text="Dodaj lub edytuj połączenie SSH", padding=12)
        fields.pack(fill="x")
        fields.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate([
            ("Alias (np. ovh-jaslo)", self.alias),
            ("Host SSH", self.host),
            ("Użytkownik SSH", self.username),
            ("Port", self.port),
        ]):
            ttk.Label(fields, text=label + ":").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 14))
            entry = ttk.Entry(fields, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            if row == 0:
                self.alias_entry = entry
        field_buttons = ttk.Frame(fields)
        field_buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        self.save_button = ttk.Button(field_buttons, text="Dodaj serwer", command=self.save_profile)
        self.save_button.pack(side="left", padx=(0, 6))
        ttk.Button(field_buttons, text="Anuluj edycję / wyczyść", command=self.reset_server_form).pack(
            side="left", padx=(0, 6))
        self.delete_button = ttk.Button(field_buttons, text="Usuń zaznaczony", command=self.delete_profile)
        self.delete_button.pack(side="left")

        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(14, 5))
        ttk.Button(actions, text="Utwórz klucz serwera", command=self.new_key).pack(
            side="left", padx=(0, 7))
        ttk.Button(actions, text="Dodaj klucz na serwer", command=self.copy_key).pack(
            side="left", padx=(0, 7))
        ttk.Button(actions, text="Połącz SSH", command=self.connect).pack(
            side="left", padx=(0, 7))
        ttk.Button(actions, text="Test połączenia", command=self.verify).pack(side="left")
        ttk.Label(tab, text=(
            "Najpierw zapisz i wybierz serwer, a następnie utwórz dla niego osobny klucz SSH z hasłem. "
            "Dodanie klucza do serwera wymaga jednorazowego uwierzytelnienia. "
            "Przy pierwszym połączeniu potwierdź odcisk klucza hosta niezależnym kanałem. "
            "Kolejne połączenia używają agenta SSH (keychain)."),
            wraplength=790, justify="left").pack(fill="x", anchor="w", pady=(9, 0))

    def build_controls(self, tab):
        ttk.Label(tab, text="Katalog 40 kontroli bezpieczeństwa",
                  font=("Sans", 12, "bold")).pack(anchor="w", pady=(0, 9))
        ttk.Label(tab, text="Wykonane są tylko podstawowe odczyty publiczne. "
                  "Kontrole wymagające SSH, WordPressa, logów i bazy danych "
                  "pozostają oznaczone jako planowane. Brak wyniku nie oznacza OK.",
                  wraplength=790).pack(anchor="w", pady=(0, 10))
        holder = ttk.Frame(tab)
        holder.pack(fill="both", expand=True)
        tree = ttk.Treeview(holder, columns=("id", "name", "access", "status"),
                            show="headings", height=19)
        for col, label, width in [
            ("id", "ID", 55), ("name", "Kontrola", 360),
            ("access", "Dostęp", 100), ("status", "Stan", 155)
        ]:
            tree.heading(col, text=label)
            tree.column(col, width=width, stretch=col == "name")
        self.enable_table_sort(tree)
        for check in bw_fleet.catalog():
            state = ("PUBLICZNY PODSTAWOWY" if check["status"] ==
                     "implemented_public_basic" else "PLANOWANY")
            tree.insert("", "end", values=(check["id"], check["name"],
                                             check["access"], state))
        scroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def build_reports(self, tab):
        ttk.Label(tab, text="Raporty i bezpieczeństwo",
                  font=("Sans", 12, "bold")).pack(anchor="w", pady=(0, 12))
        paragraphs = [
            "Testy DNS, TLS i WWW są pasywne. Nie skanują portów, nie logują się do serwisów ani nie sprawdzają podatności aktywnymi metodami.",
            "Każde uruchomienie wybranych testów tworzy jeden raport HTML w ~/beardedwolf/raporty/PAKIET.",
            "Eksport do Syncthing wymaga zaznaczenia pola na karcie Testy domen. Raporty poufne powinny pozostać lokalne, szczególnie na komputerze bez szyfrowania dysku.",
            "Profile serwerów zapisują tylko alias, host, port i użytkownika w ~/.config/beardedwolf/servers.json, a konfiguracja SSH powstaje w ~/.ssh/config. Żadnych haseł ani prywatnych kluczy nie przesyłamy do GitHuba.",
            "Każdy profil serwera ma oddzielny klucz SSH na danym komputerze, niezależny również od klucza GitHub. Autoryzacja klucza na serwerze odbywa się tylko po Twojej decyzji.",
        ]
        for paragraph in paragraphs:
            ttk.Label(tab, text=paragraph, wraplength=790, justify="left").pack(
                anchor="w", fill="x", pady=7)
        ttk.Button(tab, text="Otwórz lokalny folder raportów",
                   command=self.open_reports).pack(anchor="w", pady=10)

    def append_log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def run_tests(self):
        if self.running:
            return
        try:
            domain = bw_cli.domain_name(self.domain.get().strip())
        except Exception as exc:
            messagebox.showerror("Nieprawidłowa domena", str(exc), parent=self.root)
            return
        selected = [name for name, flag in [
            ("DNS", self.do_dns.get()), ("TLS", self.do_tls.get()), ("HTTP", self.do_http.get())
        ] if flag]
        if not selected:
            messagebox.showwarning("Brak testów", "Zaznacz co najmniej jeden test.",
                                   parent=self.root)
            return
        do_sync = self.export.get()
        if do_sync and not messagebox.askyesno(
            "Eksport do Syncthing",
            "Raport będzie synchronizowany z drugim komputerem. Potwierdzasz eksport?",
            parent=self.root
        ):
            return
        self.running = True
        self.start_button.configure(state="disabled")
        self.status.set("Trwają testy " + domain)
        self.append_log("Uruchamiam " + ", ".join(selected) + " dla " + domain)
        threading.Thread(target=self.worker, args=(domain, selected, do_sync),
                         daemon=True).start()

    def worker(self, domain, selected, do_sync):
        try:
            path, failed = bw_cli.run_suite(domain, selected, do_sync)
            self.messages.put(("result", str(path), failed))
        except Exception as exc:
            self.messages.put(("error", str(exc)))

    def pump(self):
        try:
            while True:
                event = self.messages.get_nowait()
                if event[0] == "result":
                    _, path, failed = event
                    self.last_report = Path(path)
                    self.append_log(("Zakończono z uwagami: " if failed else "Zakończono: ") + path)
                    self.status.set(("Sprawdź problemy w raporcie: " if failed else "Raport gotowy: ") + path)
                elif event[0] == "error":
                    self.append_log("Błąd: " + event[1])
                    self.status.set("Nie udało się utworzyć raportu.")
                elif event[0] == "connection":
                    self.status.set(event[1])
                    messagebox.showinfo("Test SSH", event[1], parent=self.root)
                elif event[0] == "wp_batch_site":
                    _, domain, data, error = event
                    if error:
                        self.wp_cache.pop(domain, None)
                        self.wp_errors[domain] = error
                        self.paint_dashboard_card(domain)
                        self.dashboard_hint.set("Nie sprawdzono aktualizacji " + domain +
                                                ": " + error)
                    else:
                        self.wp_errors.pop(domain, None)
                        self.wp_cache[domain] = data
                        self.paint_dashboard_card(domain)
                elif event[0] == "wp_batch_finished":
                    self.wp_batch_running = False
                    self.dashboard_hint.set(
                        f"Zakończono sprawdzanie aktualizacji WordPress na "
                        f"{event[1]} serwisach. Brak wyniku SSH oznacza brak danych, "
                        "nie brak aktualizacji."
                    )
                elif event[0] == "wp_check_done":
                    _, domain, data, error = event
                    record = self.wp_dialogs.get(domain)
                    if record:
                        if error:
                            self.wp_cache.pop(domain, None)
                            self.wp_errors[domain] = error
                            self.paint_dashboard_card(domain)
                            record["status"].set("Nie udało się sprawdzić: " + error)
                            record["data"] = None
                            record["details"].set("Core: status nieznany")
                        else:
                            self.wp_errors.pop(domain, None)
                            self.wp_cache[domain] = data
                            record["data"] = data
                            record["details"].set(
                                "Core: " + data["current_core"] +
                                (" | dostępna aktualizacja: " + ", ".join(data["core_targets"])
                                 if data["core_targets"] else " | aktualny") +
                                " | aktualizacje wtyczek: " + str(data["plugin_count"])
                            )
                            for item in record["tree"].get_children():
                                record["tree"].delete(item)
                            for index, p in enumerate(data["plugin_updates"]):
                                record["tree"].insert(
                                    "", "end", iid=str(index),
                                    values=(p["name"], p["version"], p["target"], p["status"])
                                )
                            record["status"].set(
                                "Sprawdzono aktualizacje. Zaznacz wtyczki do instalacji "
                                "albo wybierz aktualizację Core. Zmiany wymagają potwierdzenia."
                            )
                            self.paint_dashboard_card(domain)
                        self.wp_set_busy(domain, False)
                elif event[0] == "wp_update_done":
                    _, domain, kind, results, error = event
                    record = self.wp_dialogs.get(domain)
                    if record:
                        record["status"].set(
                            ("BŁĄD: " + error if error else
                             "Zakończono: " + " | ".join(results)) +
                            (" | Migrację bazy WordPress wykonano. Sprawdź działanie "
                             "strony i dziennik błędów."
                             if kind == "core" and not error else "")
                        )
                        # Lista jest nieaktualna do czasu ponownego sprawdzenia.
                        record["data"] = None
                        self.wp_cache.pop(domain, None)
                        self.paint_dashboard_card(domain)
                        self.wp_set_busy(domain, False)
                elif event[0] == "dashboard_site":
                    _, domain, data = event
                    self.dashboard_results[domain] = data
                    self.paint_dashboard_card(domain)
                elif event[0] == "dashboard_finished":
                    self.dashboard_running = False
                    current = [self.dashboard_results.get(s["domain"])
                               for s in bw_fleet.inventory()["sites"]
                               if s.get("authorized") and s.get("public_checks")]
                    ok = sum(1 for item in current if item and
                             item.get("status") in ("DOSTĘPNA", "PRZEKIEROWANIE") and
                             item.get("tls") == "WAŻNY")
                    problems = sum(1 for item in current if item and
                                   (item.get("status") not in ("DOSTĘPNA", "PRZEKIEROWANIE")
                                    or item.get("tls") != "WAŻNY"))
                    self.dashboard_hint.set(
                        f"Sprawdzono {event[1]} domen. WWW/TLS bez uwag: {ok}; "
                        f"wymaga sprawdzenia: {problems}. "
                        "Nie zastępuje audytu bezpieczeństwa. "
                        "Aktualizacje WordPress sprawdzaj osobno przez SSH."
                    )
                elif event[0] == "fleet_done":
                    results = event[1]
                    self.refresh_fleet()
                    alerts = [r for r in results if r[1] not in ("BEZ_ZMIAN", "BRAK_BASELINE")]
                    self.fleet_running = False
                    self.fleet_scan_button.configure(state="normal")
                    self.fleet_all_button.configure(state="normal")
                    self.status.set(f"Kontrola {len(results)} domen zakończona. "
                                    f"Serwisy wymagające weryfikacji: {len(alerts)}.")
                    messagebox.showinfo(
                        "Zakończono kontrolę serwisów",
                        f"Sprawdzono: {len(results)}. Wymaga weryfikacji: {len(alerts)}. "
                        "Zaznacz domenę i otwórz ostatni raport HTML. "
                        "Bez zatwierdzonego baseline wyniki są obserwacjami.",
                        parent=self.root
                    )
                if event[0] in ("result", "error"):
                    self.running = False
                    self.start_button.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(120, self.pump)

    def open_path(self, path):
        if not Path(path).exists():
            messagebox.showwarning("Brak pliku", "Nie znaleziono wskazanej ścieżki.",
                                   parent=self.root)
            return
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

    def open_last(self):
        if self.last_report is None:
            messagebox.showinfo("Brak raportu", "Najpierw uruchom testy.", parent=self.root)
            return
        self.open_path(self.last_report)

    def open_reports(self):
        directory = Path.home() / "beardedwolf" / "raporty"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.open_path(directory)

    def refresh_servers(self):
        try:
            self.profiles = bw_servers.load_profiles()
            for item in self.server_list.get_children():
                self.server_list.delete(item)
            for index, p in enumerate(self.profiles):
                self.server_list.insert("", "end", iid=str(index),
                                        values=(p["alias"], p["host"], p["user"], p["port"]))
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("Profile SSH", str(exc), parent=self.root)

    def selected_profile(self):
        selection = self.server_list.selection()
        if not selection:
            messagebox.showwarning("Wybierz serwer", "Najpierw zaznacz profil serwera.",
                                   parent=self.root)
            return None
        return self.profiles[int(selection[0])]

    def reset_server_form(self):
        self.editing_alias = None
        self.alias.set("")
        self.host.set("")
        self.username.set("")
        self.port.set("22")
        self.save_button.configure(text="Dodaj serwer")
        self.alias_entry.configure(state="normal")
        if self.server_list.selection():
            self.server_list.selection_remove(*self.server_list.selection())

    def on_server_select(self, _event=None):
        selection = self.server_list.selection()
        if not selection:
            return
        profile = self.profiles[int(selection[0])]
        self.editing_alias = profile["alias"]
        self.alias.set(profile["alias"])
        self.host.set(profile["host"])
        self.username.set(profile["user"])
        self.port.set(str(profile["port"]))
        self.save_button.configure(text="Zapisz zmiany")
        self.alias_entry.configure(state="readonly")
        self.status.set("Edytujesz profil: " + profile["alias"] +
                        ". Alias jest stały, aby zachować istniejący klucz SSH.")

    def select_server_by_alias(self, alias):
        for index, item in enumerate(self.profiles):
            if item["alias"] == alias:
                self.server_list.selection_set(str(index))
                self.server_list.focus(str(index))
                self.server_list.see(str(index))
                self.on_server_select()
                break

    def save_profile(self):
        try:
            if self.editing_alias:
                if self.alias.get() != self.editing_alias:
                    raise ValueError("Nie zmieniaj aliasu. Jest powiązany z kluczem SSH. "
                                     "Możesz edytować host, login i port.")
                profile = bw_servers.update_profile(
                    self.editing_alias, self.host.get(), self.username.get(), self.port.get())
                action = "Zaktualizowano"
            else:
                profile = bw_servers.add_profile(
                    self.alias.get(), self.host.get(), self.username.get(), self.port.get())
                action = "Dodano"
        except (OSError, ValueError) as exc:
            messagebox.showerror("Nie zapisano serwera", str(exc), parent=self.root)
            return
        self.refresh_servers()
        self.select_server_by_alias(profile["alias"])
        self.status.set(action + " profil: " + profile["alias"])

    def delete_profile(self):
        profile = self.selected_profile()
        if profile is None:
            return
        alias = profile["alias"]
        linked = [site["domain"] for site in bw_fleet.inventory()["sites"]
                  if site.get("ssh_alias") == alias]
        if linked:
            messagebox.showwarning(
                "Profil jest używany przez serwisy",
                "Najpierw zmień powiązania SSH tych serwisów:\n" + "\n".join(linked) +
                "\n\nUsunięcie profilu teraz pozostawiłoby nieaktywne odwołania.",
                parent=self.root
            )
            return
        if not messagebox.askyesno(
            "Usuń lokalny profil SSH",
            f"Usunąć profil '{alias}' z BeardedWolf Admin i sekcji SSH? "
            "Prywatny i publiczny klucz pozostaną na dysku. "
            "Nie zmienimy serwera ani pliku authorized_keys.",
            parent=self.root
        ):
            return
        try:
            bw_servers.delete_profile(alias)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Nie usunięto profilu", str(exc), parent=self.root)
            return
        self.refresh_servers()
        self.reset_server_form()
        self.status.set("Usunięto profil lokalny: " + alias + ". Klucze SSH zachowano.")

    def new_key(self):
        p = self.selected_profile()
        if p is None:
            return
        try:
            bw_servers.create_key(p)
            self.status.set("Otwarto tworzenie klucza dla " + p["alias"] + ". Ustaw unikalną passphrase.")
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Klucz SSH", str(exc), parent=self.root)

    def copy_key(self):
        p = self.selected_profile()
        if p is None:
            return
        if not messagebox.askyesno(
            "Zapis klucza na serwerze",
            "To zmieni plik authorized_keys na wskazanym serwerze. "
            "Potwierdź jego tożsamość na podstawie odcisku klucza SSH. Kontynuować?",
            parent=self.root
        ):
            return
        try:
            bw_servers.install_public_key(p)
            self.status.set("Otwarto terminal jednorazowej konfiguracji: " + p["alias"])
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Autoryzacja klucza", str(exc), parent=self.root)

    def connect(self):
        p = self.selected_profile()
        if p is None:
            return
        try:
            bw_servers.connect(p)
            self.status.set("Otwieram terminal SSH: " + p["alias"])
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Połączenie SSH", str(exc), parent=self.root)

    def verify(self):
        p = self.selected_profile()
        if p is None:
            return
        self.status.set("Sprawdzam połączenie SSH: " + p["alias"])
        threading.Thread(target=self.verify_worker, args=(p,), daemon=True).start()

    def verify_worker(self, profile):
        try:
            success, details = bw_servers.verify_connection(profile)
            result = ("Połączenie SSH działa bez hasła. " if success else
                      "Połączenie SSH nie działa jeszcze bez podawania hasła. ")
            if details:
                result += details[:1000]
        except Exception as exc:
            result = "Błąd testu SSH: " + str(exc)
        self.messages.put(("connection", result))


def main():
    root = tk.Tk()
    AdminApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
