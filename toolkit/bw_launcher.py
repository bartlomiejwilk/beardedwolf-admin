"""Entry point for BeardedWolf Operations Center.

Uses the tested original AdminApp backend; overrides presentation only.
No migrations or reconfiguration of the shared Syncthing registry.
"""
import tkinter as tk
import bw_gui
import bw_console
import bw_theme
import bw_ops_access
import bw_ops_paths
import bw_ops_saved
import bw_ops_bindings


class OperationsApp(bw_gui.AdminApp):
    def build(self):
        super().build()
        bw_ops_access.build(self)
        bw_ops_paths.build(self)
        bw_ops_saved.build(self)
        bw_ops_bindings.build(self)

    def build_dashboard(self, tab):
        self.dashboard_search = tk.StringVar(value="")
        bw_console.build(self, tab)

    def draw_dashboard(self):
        bw_console.draw(self)

    def paint_dashboard_card(self, domain):
        bw_console.paint(self, domain)


def main():
    root = tk.Tk()
    bw_theme.apply(root)
    root.geometry("1450x890")
    root.minsize(1100, 690)
    root.title("BeardedWolf | Operations Center")
    OperationsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
