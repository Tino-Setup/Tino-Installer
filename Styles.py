from tkinter import ttk

MAIN_COLOR = "#6580E1"
PROGRESS_BAR = "#49FBA8"


def get_style():
    """Create and return a configured ttk.Style instance for the installer."""
    style = ttk.Style()
    style.theme_use("clam")

    style.configure("Content.TFrame", background="white")
    style.configure("Content.TLabel", background="white", foreground="black",
                    font=("Sans", 11))
    style.configure("Hyperlink.TLabel", background="white", foreground=MAIN_COLOR,
                    font=("Sans", 9, "bold"))
    style.configure("Title.TLabel", background="white", foreground=MAIN_COLOR,
                    font=("Sans", 16, "bold"))
    style.configure("Heading.TLabel", background="white", foreground="black",
                    font=("Sans", 12, "bold"))
    style.configure("Content.TCheckbutton", background="white", foreground="black",
                    font=("Sans", 11))
    style.map("Content.TCheckbutton", background=[("active", "white")],
              foreground=[("active", MAIN_COLOR)])
    style.configure("Content.TButton", background="white", foreground="black",
                    font=("Sans", 11, "bold"))
    style.map("Content.TButton",
              background=[("active", "#E8ECFA"), ("pressed", "#D0D8F4")],
              foreground=[("active", MAIN_COLOR), ("pressed", MAIN_COLOR)])

    style.configure("Brand.TFrame", background="white")
    style.configure("Logo.TLabel", background="white")

    style.configure("TProgressbar", background=PROGRESS_BAR, troughcolor="white",
                    thickness=18)
    style.layout("TProgressbar", [('Horizontal.TProgressbar.trough',
                                   {'children': [('Horizontal.TProgressbar.pbar',
                                                  {'side': 'left', 'sticky': 'ns'})]})])


    return style