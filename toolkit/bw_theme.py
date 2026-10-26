"""BeardedWolf Admin: dependency-free dark operator theme for Tkinter."""
from tkinter import ttk

COLORS = {
    "bg": "#0B1220", "panel": "#142339", "surface": "#101D30",
    "fg": "#ECF5FF", "muted": "#A6BAD0", "cyan": "#36D6EC",
    "green": "#45D9A3", "amber": "#FFC777", "red": "#FB7585",
    "border": "#29415C", "selected": "#1B506D",
}


def apply(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    c = COLORS
    style.configure(".", background=c["bg"], foreground=c["fg"],
                    font=("DejaVu Sans", 10))
    style.configure("TFrame", background=c["bg"])
    style.configure("TLabel", background=c["bg"], foreground=c["fg"])
    style.configure("TLabelFrame", background=c["panel"],
                    foreground=c["fg"], bordercolor=c["border"])
    style.configure("TLabelFrame.Label", background=c["panel"],
                    foreground=c["fg"], font=("DejaVu Sans", 10, "bold"))
    style.configure("TNotebook", background=c["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", padding=(14, 10), background=c["panel"],
                    foreground=c["muted"])
    style.map("TNotebook.Tab", background=[("selected", c["selected"]),
                                            ("active", "#29415C")],
              foreground=[("selected", c["fg"])])
    style.configure("TButton", padding=(9, 8), background=c["panel"],
                    foreground=c["fg"], bordercolor=c["border"])
    style.map("TButton", background=[("active", c["selected"])],
              foreground=[("active", c["fg"])])
    style.configure("Accent.TButton", background="#167D9E",
                    foreground="#FFFFFF", padding=(14, 9),
                    font=("DejaVu Sans", 10, "bold"))
    style.map("Accent.TButton", background=[("active", "#1598BC")])
    style.configure("Treeview", background=c["surface"], fieldbackground=c["surface"],
                    foreground=c["fg"], rowheight=34, borderwidth=0)
    style.map("Treeview", background=[("selected", c["selected"])],
              foreground=[("selected", "#FFFFFF")])
    style.configure("Treeview.Heading", background="#223750", foreground=c["fg"],
                    padding=(7, 10), font=("DejaVu Sans", 10, "bold"))
    style.map("Treeview.Heading", background=[("active", "#31506D")])
    style.configure("TEntry", fieldbackground=c["surface"], foreground=c["fg"])
    style.configure("TCombobox", fieldbackground=c["surface"],
                    foreground=c["fg"])
    style.map("TCombobox", fieldbackground=[("readonly", c["surface"])],
              foreground=[("readonly", c["fg"])])
    root.option_add("*TCombobox*Listbox.background", c["surface"])
    root.option_add("*TCombobox*Listbox.foreground", c["fg"])
    root.configure(bg=c["bg"])
