#!/usr/bin/env python3
"""BeardedWolf Admin: graficzny panel diagnostyki i połączeń SSH (Kali XFCE)."""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import bw_servers
import bw_fleet

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
        self.root.geometry("890x710")
        self.root.minsize(720, 570)
        self.messages = queue.Queue()
        self.last_report = None
        self.profiles = []
        self.managed_sites = []
        self.fleet_running = False
        self.last_fleet_report = None
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

        self.build()
        self.refresh_servers()
        self.root.after(120, self.pump)

    def build(self):
        frame = ttk.Frame(self.root, padding=14)
        frame.pack(fill="both", expand=True)

        title = ttk.Label(frame, text="BeardedWolf Admin", font=("Sans", 19, "bold"))
        title.pack(anchor="w")
        ttk.Label(frame, text="Audyt pasywny domen i szybkie połączenia z serwerami",
                  font=("Sans", 10)).pack(anchor="w", pady=(0, 12))

        tabs = ttk.Notebook(frame)
        tabs.pack(fill="both", expand=True)
        tests = ttk.Frame(tabs, padding=14)
        servers = ttk.Frame(tabs, padding=14)
        fleet = ttk.Frame(tabs, padding=14)
        reports = ttk.Frame(tabs, padding=14)
        tabs.add(fleet, text="  Wszystkie serwisy  ")
        tabs.add(tests, text="  Testy domen  ")
        tabs.add(servers, text="  Serwery SSH  ")
        tabs.add(reports, text="  Raporty i informacje  ")
        self.build_fleet(fleet)
        self.build_tests(tests)
        self.build_servers(servers)
        self.build_reports(reports)

        ttk.Separator(frame).pack(fill="x", pady=(10, 8))
        ttk.Label(frame, textvariable=self.status, wraplength=820).pack(
            anchor="w", fill="x")

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
                                      columns=("domain", "group", "type", "authorized", "last"), height=13)
        for col, label, width in [
            ("domain", "Domena", 250), ("group", "Grupa", 110),
            ("type", "Platforma", 105), ("authorized", "Zakres", 115),
            ("last", "Ostatnia kontrola", 135)
        ]:
            self.site_list.heading(col, text=label)
            self.site_list.column(col, width=width, stretch=col == "domain")
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.site_list.yview)
        self.site_list.configure(yscrollcommand=scrollbar.set)
        self.site_list.pack(side="left", fill="both", expand=True)
        self.site_list.bind("<Double-1>", lambda _evt: self.edit_site())
        scrollbar.pack(side="right", fill="y")
        manage = ttk.Frame(tab)
        manage.pack(anchor="w", fill="x", pady=(8, 0))
        ttk.Button(manage, text="Dodaj serwis", command=self.add_site).pack(side="left", padx=(0, 6))
        ttk.Button(manage, text="Edytuj serwis", command=self.edit_site).pack(side="left", padx=(0, 6))
        ttk.Button(manage, text="Usuń z rejestru", command=self.remove_site).pack(side="left", padx=(0, 6))
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
                self.site_list.insert("", "end", iid=str(index), values=(
                    site["domain"], site["group"], site["type"],
                    "POTWIERDZONY" if site.get("authorized") else "DO POTWIERDZENIA",
                    last
                ))
                if site["domain"] == selected_domain:
                    self.site_list.selection_set(str(index))
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
