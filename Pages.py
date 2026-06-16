import tkinter as tk
from tkinter import ttk

from i18n import _


class InfoPage(ttk.Frame):
    """Base class for License / Pre-Install / Post-Install pages (removes duplication)"""
    def __init__(self, parent, title: str, text_key: str, data, is_license: bool = False):
        """Initialize the InfoPage."""
        super().__init__(parent, style="Content.TFrame")

        ttk.Label(self, text=title, style="Heading.TLabel").pack(anchor="w", pady=(10, 5))
        if is_license:
            ttk.Label(self, text=_("Please read the following License Agreement carefully. By installing you agree to these terms."), style="Content.TLabel", wraplength=600).pack(anchor="w")
        else:
            ttk.Label(self, text=_("Please read the following information carefully."), style="Content.TLabel", wraplength=600).pack(anchor="w")

        container = ttk.Frame(self, style="Content.TFrame")
        container.pack(fill="both", expand=True, padx=5, pady=5)

        self.text_box = tk.Text(container, height=12, wrap="word",
                             font=("Sans", 10),
                             bg="white", fg="#000000",
                             relief="sunken", borderwidth=1)
        self.scroll = ttk.Scrollbar(container, orient="vertical", command=self.text_box.yview)
        self.text_box.configure(yscrollcommand=self.scroll.set)

        self.scroll.pack(side="right", fill="y")
        self.text_box.pack(side="left", fill="both", expand=True)

        self.text_box.insert("1.0", getattr(data, text_key, ""))

        self.text_box.configure(state="disabled")


class WelcomePage(ttk.Frame):
    """The initial welcome page of the installer."""
    def __init__(self, parent, data, logo=None):
        """Initialize the WelcomePage."""
        super().__init__(parent, style="Content.TFrame")
        
        if logo:
            self.logo_label = ttk.Label(self, image=logo, style="Logo.TLabel")
            self.logo_label.pack(pady=(20, 0))

        ttk.Label(self, text=_("Welcome to the {} Setup Wizard").format(data.local.application_name),
              style="Title.TLabel", wraplength=600, justify="center").pack(pady=(20, 10))
        
        ttk.Label(self, text=_("This wizard will guide you through the installation of\n"
                         "{} version {} on your computer.\n\n"
                         "Click Next to continue or Cancel to abort the installation.").format(data.local.application_name, data.application_version),
              style="Content.TLabel", justify="center", wraplength=600).pack(pady=10)


class LicensePage(InfoPage):
    """Page displaying the software license agreement."""
    def __init__(self, parent, accept_var, update_callback, data):
        """Initialize the LicensePage."""
        super().__init__(parent, _("License Agreement"),
                         "application_license_text", data, is_license=True)

        self.accept_var = accept_var
        self.accept_cb = ttk.Checkbutton(
            self,
            text=_("I accept the terms of the license agreement"),
            variable=self.accept_var,
            command=update_callback,
            style="Content.TCheckbutton"
        )
        self.accept_cb.pack(anchor="w", pady=8)


class PreInstallInfoPage(InfoPage):
    """Page displaying pre-installation information."""
    def __init__(self, parent, data):
        """Initialize the PreInstallInfoPage."""
        super().__init__(parent, _("Information"),
                         "application_pre_install_information_text", data)


class PostInstallInfoPage(InfoPage):
    """Page displaying post-installation information."""
    def __init__(self, parent, data):
        """Initialize the PostInstallInfoPage."""
        super().__init__(parent, _("Information"),
                         "application_post_install_information_text", data)




class AdditionalTasksPage(ttk.Frame):
    """Page allowing the user to select optional additional installation tasks."""
    def __init__(self, parent, data, allowedtasks_var: list):
        """Initialize the AdditionalTasksPage."""
        super().__init__(parent, style="Content.TFrame")

        ttk.Label(self, text=_("Additional Tasks"), style="Heading.TLabel").pack(anchor="w", pady=(10, 5))
        ttk.Label(self, text=_("Select any additional tasks for {}.\n").format(data.local.application_name),
              style="Content.TLabel", justify="left").pack(anchor="w", pady=5)

        self.allowedtasks_var = allowedtasks_var
        self.check_vars = []

        for task in data.local.application_additional_tasks:
            var = tk.BooleanVar(value=False)
            self.check_vars.append(var)
            ttk.Checkbutton(
                self,
                text=task.name,
                variable=var,
                command=lambda b=var, t=task: self._toggle_task(b, t),
                style="Content.TCheckbutton"
            ).pack(anchor="w", pady=2)


    def _toggle_task(self, var: tk.BooleanVar, task):
        """Toggle an additional task in the allowed tasks list."""
        if var.get():
            if task not in self.allowedtasks_var:
                self.allowedtasks_var.append(task)
        else:
            if task in self.allowedtasks_var:
                self.allowedtasks_var.remove(task)


class ReadyPage(ttk.Frame):
    """Page summarizing the installation choices before beginning."""
    def __init__(self, parent, data, dest_var, allowedtasks_var: list):
        """Initialize the ReadyPage."""
        super().__init__(parent, style="Content.TFrame")

        ttk.Label(self, text=_("Ready to Install"), style="Heading.TLabel").pack(anchor="w", pady=(10, 5))
        ttk.Label(self, text=_("The wizard is ready to begin installing {}.\n\n"
                         "Click Install to begin the installation or click Back to change any settings.").format(data.local.application_name),
              style="Content.TLabel", wraplength=600, justify="left").pack(anchor="w")

        container = ttk.Frame(self, style="Content.TFrame")
        container.pack(fill="both", expand=True, padx=5, pady=5)

        self.summary_box = tk.Text(
            container, height=12, wrap="word",
            font=("Sans", 10), bg="white", fg="#000000",
            relief="sunken", borderwidth=1
        )
        scroll = ttk.Scrollbar(container, orient="vertical", command=self.summary_box.yview)
        self.summary_box.configure(yscrollcommand=scroll.set)

        scroll.pack(side="right", fill="y")
        self.summary_box.pack(side="left", fill="both", expand=True)

        self.data = data
        self.dest_var = dest_var
        self.allowedtasks_var = allowedtasks_var

        self.refresh_summary()

    def refresh_summary(self):
        """Update the summary text box"""
        self.summary_box.configure(state="normal")
        self.summary_box.delete("1.0", "end")
        
        summary = []
        summary.append(_("Installation Path:\n  {}\n").format(self.dest_var.get()))
        summary.append(_("Executable Path:\n  {}\n").format(self.data.application_executable_path))
        
        if self.data.application_icon_path:
            summary.append(_("Icon Path:\n  {}\n").format(self.data.application_icon_path))
            
        if self.data.application_desktop_path:
            summary.append(_("Desktop Path:\n  {}\n").format(self.data.application_desktop_path))
            
        if self.allowedtasks_var:
            tasks_str = "\n  ".join([t.name for t in self.allowedtasks_var])
            summary.append(_("\nAdditional Tasks:\n  {}").format(tasks_str))

        self.summary_box.insert("1.0", "\n".join(summary))
        self.summary_box.configure(state="disabled")


class InstallingPage(ttk.Frame):
    """A2: Exposes clean update methods instead of raw widget access."""
    def __init__(self, parent, data):
        """Initialize the InstallingPage."""
        super().__init__(parent, style="Content.TFrame")
        ttk.Label(self, text=_("Installing {}...").format(data.local.application_name),
              style="Heading.TLabel").pack(pady=20)

        self._progress = ttk.Progressbar(self, mode="determinate", length=400,
                                    style="TProgressbar")
        self._progress.pack(pady=10)

        self._status_label = ttk.Label(self, text=_("Preparing files..."),
                                  style="Content.TLabel")
        self._status_label.pack()

    def update_progress(self, value: float):
        """Set progress bar value (0-100)."""
        self._progress["value"] = value

    def update_status(self, text: str):
        """Set the status label text."""
        self._status_label.config(text=text)


class RollbackPage(ttk.Frame):
    """Page that appears when user cancels during installation.
    A2: Exposes clean update methods."""
    def __init__(self, parent):
        """Initialize the RollbackPage."""
        super().__init__(parent, style="Content.TFrame")

        self.title_label = ttk.Label(self, text=_("Installation Cancelled"),
                                 style="Title.TLabel")
        self.title_label.pack(pady=(30))

        self.message_label = ttk.Label(
            self,
            text=_("Rolling back changes to restore your system.\nPlease wait..."),
            style="Content.TLabel",
            justify="center",
            wraplength=520
        )
        self.message_label.pack(pady=(0, 25))

        self._progress = ttk.Progressbar(
            self,
            mode="indeterminate",
            length=420,
            style="TProgressbar"
        )
        self._progress.pack(pady=15)

        self._status_label = ttk.Label(self, text=_("Removing files..."),
                                  style="Content.TLabel")
        self._status_label.pack(pady=10)

    def start_animation(self):
        """Start the indeterminate progress animation."""
        self._progress.start(30)

    def stop_animation(self):
        """Stop the indeterminate progress animation."""
        self._progress.stop()

    def update_status(self, text: str):
        """Set the status label text."""
        self._status_label.config(text=text)


class FinishPage(ttk.Frame):
    """The final page displayed when installation completes or is cancelled."""
    def __init__(self, parent, logo=None):
        """Initialize the FinishPage."""
        super().__init__(parent, style="Content.TFrame")
        
        if logo:
            self.logo_label = ttk.Label(self, image=logo, style="Logo.TLabel")
            self.logo_label.pack(pady=(30, 0))

        self.title_label = ttk.Label(self, text="", style="Title.TLabel", justify="center")
        self.title_label.pack(pady=(20, 10))
        self.message_label = ttk.Label(self, text="", style="Content.TLabel", justify="center", wraplength=550)
        self.message_label.pack(pady=10)