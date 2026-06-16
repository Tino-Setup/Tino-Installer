import webbrowser

import tkinter as tk
from tkinter import ttk

from Data import load_data, TinoConfig, AdditionalTask
from Pages import (
    WelcomePage, LicensePage, PreInstallInfoPage, PostInstallInfoPage,
    AdditionalTasksPage, ReadyPage, InstallingPage, RollbackPage, FinishPage,
)
from Styles import get_style
from Engine import InstallationEngine
from i18n import _, set_language, get_available_languages, BASE_DIR
import os
import sys
import threading
from Elevation import check_and_elevate, needs_elevation
from Data import refresh_texts


class LanguageSelectionDialog(tk.Tk):
    """Dialog for selecting the installation language."""
    def __init__(self, languages):
        """Initialize the LanguageSelectionDialog."""
        super().__init__()
        self.title(_("Tino Setup"))
        self.geometry("400x240")
        self.resizable(False, False)
        self.configure(bg="white")

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.cancelled = False

        self.style = get_style()
        
        self.result = "en_US"
        self.langs = languages

        main_frame = ttk.Frame(self, style="Content.TFrame", padding="30")
        main_frame.pack(fill="both", expand=True)
        
        ttk.Label(main_frame, text=_("Select Language"), 
                  style="Title.TLabel").pack(pady=(0, 20))

        initial_val = self.langs.get("en_US", "English (United States)")
        self.lang_var = tk.StringVar(value=initial_val)
        
        self.combo = ttk.Combobox(main_frame, textvariable=self.lang_var, 
                                  values=list(self.langs.values()), state="readonly", width=35)
        self.combo.pack(pady=10)
        
        self.ok_btn = ttk.Button(main_frame, text=_("OK"), command=self.on_ok, 
                                 style="Content.TButton", width=-15)
        self.ok_btn.pack(pady=20)

        self.combo.focus_set()
        self.bind("<Return>", lambda e: self.on_ok())

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        
    def on_ok(self):
        """Handle the OK button click to confirm language selection."""
        selected_val = self.lang_var.get()
        for code, name in self.langs.items():
            if name == selected_val:
                self.result = code
                break
        self.destroy()

    def on_close(self):
        """Handle the window close event to cancel selection."""
        self.cancelled = True
        self.destroy()


class TinoDialog(tk.Toplevel):
    """A premium, localizable replacement for standard messageboxes"""
    def __init__(self, parent, title, message, type="ok"):
        """Initialize the TinoDialog."""
        super().__init__(parent)
        self.title(title)
        self.configure(bg="white")
        self.resizable(False, False)
        self.result = None

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.transient(parent)
        self.grab_set()
        
        main_frame = ttk.Frame(self, style="Content.TFrame", padding=25)
        main_frame.pack(fill="both", expand=True)

        content_frame = ttk.Frame(main_frame, style="Content.TFrame")
        content_frame.pack(fill="both", expand=True)
        
        ttk.Label(content_frame, text=message, style="Content.TLabel", 
                  wraplength=350, justify="left").pack(pady=(0, 20))

        btn_frame = ttk.Frame(main_frame, style="Content.TFrame")
        btn_frame.pack(fill="x", side="bottom")
        
        if type == "yesno":
            ttk.Button(btn_frame, text=_("Yes"), width=-10, 
                       command=self.on_yes, style="Content.TButton").pack(side="right", padx=5)
            ttk.Button(btn_frame, text=_("No"), width=-10, 
                       command=self.on_no, style="Content.TButton").pack(side="right")
        else:
            ttk.Button(btn_frame, text=_("OK"), width=-10, 
                       command=self.on_ok, style="Content.TButton").pack(side="right")

        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        py = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{px}+{py}")
        
        self.wait_window()

    def on_yes(self):
        """Handle the Yes button click."""
        self.result = True
        self.destroy()

    def on_no(self):
        """Handle the No button click."""
        self.result = False
        self.destroy()

    def on_ok(self):
        """Handle the OK button click."""
        self.result = True
        self.destroy()

    def on_cancel(self):
        """Handle the dialog cancellation."""
        self.result = False
        self.destroy()


class App(tk.Tk):
    """Main application class for the Tino Installer wizard."""
    def __init__(self, data: TinoConfig):
        """Initialize the installer application."""
        super().__init__()
        self.style = get_style()
        self.data = data
        self.engine = InstallationEngine(data)

        self.title(_("{} Setup").format(self.data.local.application_name))
        self.wm_protocol("WM_DELETE_WINDOW", self.cancel_setup)
        self.geometry("700x500")
        self.resizable(False, False)

        self.main_area = ttk.Frame(self, style="Content.TFrame")
        self.main_area.pack(side="right", fill="both", expand=True)

        self.content = ttk.Frame(self.main_area, style="Content.TFrame")
        self.content.pack(fill="both", expand=True, padx=20, pady=10)

        ttk.Separator(self.main_area, orient="horizontal").pack(fill="x")

        self.btn_frame = ttk.Frame(self.main_area, style="Content.TFrame")
        self.btn_frame.pack(fill="x", padx=15, pady=15)

        self.app_author_label = ttk.Label(self.btn_frame,
                                      text=_("{} by {}").format(self.data.local.application_name, self.data.application_author),
                                      style="Hyperlink.TLabel", wraplength=300)

        self.back_btn = ttk.Button(self.btn_frame, text=_("Back"), width=-10,
                               command=self.go_back, style="Content.TButton")
        self.next_btn = ttk.Button(self.btn_frame, text=_("Next"), width=-10,
                               command=self.go_next, style="Content.TButton")
        self.cancel_btn = ttk.Button(self.btn_frame, text=_("Cancel"), width=-10,
                                 command=self.cancel_setup, style="Content.TButton")

        self.btn_frame.columnconfigure(1, weight=1)
        self.app_author_label.grid(row=0, column=0, sticky="w")
        self.back_btn.grid(row=0, column=2, padx=(0, 5))
        self.next_btn.grid(row=0, column=3, padx=5)
        self.cancel_btn.grid(row=0, column=4, padx=(5, 0))

        website_url = self.data.application_website
        if website_url:
            self.app_author_label.config(cursor="hand2")
            self.app_author_label.bind("<Button-1>",
                                       lambda e: webbrowser.open_new(website_url))

        self.page_order = self._build_page_order()
        self.pages = {}
        self.current_page = ""
        self.current_frame = None

        self.accept_var = tk.BooleanVar()
        self.dest_var = tk.StringVar(value=self.data.application_installation_path)
        self.allowedtasks_var: list[AdditionalTask] = []

        self.logo = None
        if self.data.application_icon:
            try:
                raw_logo = tk.PhotoImage(file=os.path.join(BASE_DIR, self.data.application_icon))
                natural_h = raw_logo.height()
                factor = max(1, round(natural_h / 120))
                self.logo = raw_logo.subsample(factor, factor)
            except Exception:
                pass

        self.create_pages()

        self._setup_engine_callbacks()

        self.show_page('WelcomePage')

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _setup_engine_callbacks(self):
        """Connect engine events to UI updates (always via after() for thread safety)."""
        self.engine.on_progress = lambda pct, fn: self.after(0, self._on_progress, pct, fn)
        self.engine.on_status = lambda msg: self.after(0, self._on_status, msg)
        self.engine.on_error = lambda msg: self.after(0, self._handle_installation_error, msg)
        self.engine.on_finished = lambda: self.after(500, self._finish_installation)
        self.engine.on_task_warning = lambda t, m: self.after(0, self._on_task_warning, t, m)

    def _on_progress(self, percent, filename):
        """Update progress bar and status from engine callback."""
        if not self.engine.is_running:
            return
        installing_page = self.pages['InstallingPage']
        installing_page.update_progress(percent)
        installing_page.update_status(_("Extracting: {}").format(filename))

    def _on_status(self, message):
        """Update status label from engine callback."""
        self.pages['InstallingPage'].update_status(message)

    def _on_task_warning(self, title, message):
        """Show a non-fatal warning dialog (C4: replaces messagebox.showwarning)."""
        TinoDialog(self, title, message, type="ok")

    def _build_page_order(self) -> list[str]:
        """Determine the sequence of wizard pages based on configuration."""
        order = ["WelcomePage"]
        if self.data.local.application_license:
            order.append("LicensePage")
        if self.data.local.application_pre_install_information:
            order.append("PreInstallInfoPage")
        if self.data.local.application_additional_tasks:
            order.append("AdditionalTasksPage")
        order.extend(["ReadyPage", "InstallingPage"])
        if self.data.local.application_post_install_information:
            order.append("PostInstallInfoPage")
        order.append("FinishPage")
        return order

    def create_pages(self):
        """Instantiate every page as its own class"""
        pages_to_create = list(self.page_order)
        if "RollbackPage" not in pages_to_create:
            pages_to_create.append("RollbackPage")

        for page_name in pages_to_create:
            if page_name == "WelcomePage":
                self.pages[page_name] = WelcomePage(self.content, data=self.data, logo=self.logo)
            elif page_name == "LicensePage":
                self.pages[page_name] = LicensePage(self.content, self.accept_var,
                                                    self.update_next_button, data=self.data)
            elif page_name == "PreInstallInfoPage":
                self.pages[page_name] = PreInstallInfoPage(self.content, data=self.data)
            elif page_name == "AdditionalTasksPage":
                self.pages[page_name] = AdditionalTasksPage(self.content, data=self.data,
                                                            allowedtasks_var=self.allowedtasks_var)
            elif page_name == "ReadyPage":
                self.pages[page_name] = ReadyPage(self.content, data=self.data,
                                                  dest_var=self.dest_var,
                                                  allowedtasks_var=self.allowedtasks_var)
            elif page_name == "InstallingPage":
                self.pages[page_name] = InstallingPage(self.content, data=self.data)
            elif page_name == "PostInstallInfoPage":
                self.pages[page_name] = PostInstallInfoPage(self.content, data=self.data)
            elif page_name == "RollbackPage":
                self.pages[page_name] = RollbackPage(self.content)
            elif page_name == "FinishPage":
                self.pages[page_name] = FinishPage(self.content, logo=self.logo)

    def show_page(self, page_name: str):
        """Display the specified wizard page and update navigation buttons."""
        if self.current_frame:
            self.current_frame.pack_forget()

        self.current_page = page_name
        self.current_frame = self.pages[page_name]
        self.current_frame.pack(fill="both", expand=True)

        self.next_btn.config(text=_("Next"), state="normal")

        if self.current_page in ("WelcomePage", "InstallingPage", "PostInstallInfoPage", "FinishPage", "RollbackPage"):
            self.back_btn.grid_remove()
        else:
            self.back_btn.grid()

        if self.current_page in ("InstallingPage", "FinishPage", "PostInstallInfoPage", "RollbackPage"):
            self.cancel_btn.grid_remove()
        else:
            self.cancel_btn.grid()

        if self.current_page == "InstallingPage":
            self.next_btn.config(state="disabled")
            self.start_installation()
        elif self.current_page == "RollbackPage":
            self.next_btn.config(state="disabled")
            self.start_rollback()
        elif self.current_page == "FinishPage":
            self._configure_finish_page()
            self.next_btn.config(text=_("Finish"), state="normal")
        elif self.current_page == "LicensePage":
            self.update_next_button()
        elif self.current_page == "ReadyPage":
            self.pages['ReadyPage'].refresh_summary()
            self.next_btn.config(text=_("Install"), state="normal")
    
    def start_rollback(self):
        """Called automatically when RollbackPage is shown"""
        rollback_page = self.pages["RollbackPage"]
        rollback_page.start_animation()

        target_dir = self.dest_var.get()

        def do_rollback():
            self.engine.on_rollback_step = lambda msg: self.after(0, rollback_page.update_status, msg)
            self.engine.on_rollback_finished = lambda: self.after(600, self._on_rollback_finished)
            self.engine.perform_rollback(target_dir)

        def wait_and_rollback():
            self.engine.wait_for_thread(timeout=5.0)
            do_rollback()

        threading.Thread(target=wait_and_rollback, daemon=True).start()

    def _on_rollback_finished(self):
        """Called when engine finishes rollback."""
        self.pages["RollbackPage"].stop_animation()
        self.show_page("FinishPage")
    
    def _configure_finish_page(self):
        """Show different text depending on whether we rolled back or completed normally"""
        finish = self.pages["FinishPage"]
        if hasattr(self, '_rollback_performed') and self._rollback_performed:
            finish.title_label.config(text=_("Installation Cancelled"))
            finish.message_label.config(
                text=_("{} installation was cancelled.\n\nClick Finish to close the wizard.").format(self.data.local.application_name)
            )
        else:
            finish.title_label.config(text=_("Installation Complete"))
            finish.message_label.config(
                text=_("{} has been successfully installed.\n\nClick Finish to close the wizard.").format(self.data.local.application_name)
            )

    def get_next_page(self) -> str | None:
        """Get the name of the next page in the wizard sequence."""
        try:
            idx = self.page_order.index(self.current_page)
            return self.page_order[idx + 1] if idx + 1 < len(self.page_order) else None
        except ValueError:
            return None

    def get_prev_page(self) -> str | None:
        """Get the name of the previous page in the wizard sequence."""
        try:
            idx = self.page_order.index(self.current_page)
            return self.page_order[idx - 1] if idx - 1 >= 0 else None
        except ValueError:
            return None

    def update_next_button(self):
        """Called by the license checkbox"""
        if self.current_page == "LicensePage":
            self.next_btn.config(state="normal" if self.accept_var.get() else "disabled")

    def go_back(self):
        """Navigate to the previous page."""
        prev = self.get_prev_page()
        if prev:
            self.show_page(prev)

    def go_next(self):
        """Navigate to the next page or finish the installation."""
        if self.current_page == "FinishPage":
            self.destroy()
        else:
            next_page = self.get_next_page()
            if next_page:
                self.show_page(next_page)


    def start_installation(self):
        """Validates environment, then delegates to engine."""
        self.pages['InstallingPage'].update_progress(0)
        self._rollback_performed = False
        
        target_dir = self.dest_var.get()

        error = self.engine.validate_target(target_dir)
        if error:
            self._handle_installation_error(error)
            return

        archive_path = self.engine.find_archive()
        if not archive_path:
            self._handle_installation_error(_("Archive file not found."))
            return

        self.engine.start_install(target_dir, archive_path, list(self.allowedtasks_var))

    def _handle_installation_error(self, error_msg):
        """Handle an error during installation by showing a dialog and rolling back."""
        self.engine.request_cancel()
        self._rollback_performed = True
        TinoDialog(self, _("Installation Error"), 
                   _("An error occurred during installation:\n\n{}").format(error_msg), 
                   type="ok")
        self.show_page("RollbackPage")

    def _finish_installation(self):
        """Handle the successful completion of the installation process."""
        if not self.engine.is_running:
            return
        self.pages['InstallingPage'].update_status(_("Installation complete!"))
        if self.data.local.application_post_install_information:
            self.after(800, lambda: self.show_page("PostInstallInfoPage"))
        else:
            self.after(800, lambda: self.show_page("FinishPage"))

    def cancel_setup(self):
        """Prompt the user and cancel the installation if confirmed."""
        if self.current_page == "RollbackPage":
            TinoDialog(self, _("Rolling Back"), 
                       _("Please wait while the rollback finishes."), 
                       type="ok")
            return

        if self.current_page in ("WelcomePage", "FinishPage", "PostInstallInfoPage"):
            self.destroy()
            return

        dialog = TinoDialog(self, _("Exit Setup"),
                            _("Are you sure you want to cancel the installation?\n\n"
                              "Any changes made so far will be lost."),
                            type="yesno")
        
        if dialog.result:
            if self.current_page == "InstallingPage":
                self.engine.request_cancel()
                self._rollback_performed = True
                self.pages['InstallingPage'].update_progress(0)
                self.show_page("RollbackPage")
            else:
                self.destroy()


if __name__ == "__main__":
    
    data = load_data()

    paths_to_check = [
        data.application_installation_path,
        data.application_executable_path,
        data.application_icon_path,
        data.application_desktop_path,
    ]
    
    if any(p and needs_elevation(p) for p in paths_to_check):
        check_and_elevate()

    available_langs = get_available_languages(data)
    if len(available_langs) > 1:
        dialog = LanguageSelectionDialog(available_langs)
        dialog.mainloop()
        if getattr(dialog, 'cancelled', False):
            sys.exit(0)

        data.current_lang = dialog.result
        set_language(dialog.result)
    else:
        lang_code = next(iter(available_langs.keys()))
        data.current_lang = lang_code
        set_language(lang_code)

    refresh_texts(data)

    app = App(data=data)

    icon_path = data.application_icon
    if icon_path:
        try:
            icon = tk.PhotoImage(file=os.path.join(BASE_DIR, icon_path))
            app.iconphoto(True, icon)
        except Exception:
            pass
            
    app.mainloop()