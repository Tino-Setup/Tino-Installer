"""
Engine.py — Installation engine (business logic separated from UI).

Handles: archive discovery, decompression, script execution,
symlink/desktop-file creation, rollback, and cleanup.
All file-system and subprocess work lives here; the UI layer
communicates via callbacks.
"""

import glob
import os
import shlex
import shutil
import subprocess
import threading
from typing import Callable, List, Optional

from Compression import decompress
from Data import TinoConfig, AdditionalTask
from Elevation import is_root, fix_ownership
from i18n import _, BASE_DIR





class InstallationEngine:
    """Encapsulates every file-system operation the installer performs."""

    def __init__(self, data: TinoConfig):
        """Initialize the installation engine with the given configuration."""
        self.data = data

        self._running = False
        self._install_thread: Optional[threading.Thread] = None
        self._target_dir_preexisted = False
        self._extracted_files: dict[str, None] = {}

        self.on_progress: Optional[Callable] = None
        self.on_status: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_finished: Optional[Callable] = None
        self.on_rollback_step: Optional[Callable] = None
        self.on_rollback_finished: Optional[Callable] = None
        self.on_task_warning: Optional[Callable] = None

    @property
    def is_running(self) -> bool:
        """Check if the installation process is currently running."""
        return self._running

    @property
    def extracted_files(self) -> list:
        """Return list in insertion order (needed for reversed rollback)."""
        return list(self._extracted_files.keys())

    def validate_target(self, target_dir: str) -> Optional[str]:
        """
        Returns an error message if we can't write to *target_dir*,
        or None if everything looks fine.

        Walks up the path to find the first existing ancestor and checks
        write permission there (fixes C3).
        """
        check_path = target_dir.rstrip("/")
        while check_path and not os.path.exists(check_path):
            check_path = os.path.dirname(check_path)

        if not check_path:
            check_path = "/"

        if not os.access(check_path, os.W_OK) and not is_root():
            return _(
                "You do not have permission to write to {}.\n\n"
                "Please run the installer as root or choose a different location."
            ).format(target_dir)
        return None

    def find_archive(self) -> Optional[str]:
        """Locate the archive file. Returns path or None."""
        ext_map = {"lzma": ".tar.xz", "gzip": ".tar.gz", "bz2": ".tar.bz2"}
        expected_ext = ext_map.get(self.data.application_compression_type, ".tar.xz")

        app_name_slug = self.data.application_name_slug or self.data.local.application_name.replace(" ", "_")
        candidate3_base = f"{app_name_slug}-{self.data.application_version}"

        def search_dir(d):
            candidates = [
                os.path.join(d, "installer" + expected_ext),
                os.path.join(d, candidate3_base + expected_ext)
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

            for ext in ext_map.values():
                for pattern in ["installer.tar.*", f"{candidate3_base}.tar.*", f"*{ext}"]:
                    matches = glob.glob(os.path.join(d, pattern))
                    if matches:
                        return matches[0]
            return None

        return search_dir(BASE_DIR) or search_dir(".")


    def start_install(self, target_dir: str, archive_path: str,
                      selected_tasks: List[AdditionalTask]):
        """Begin installation in a background thread."""
        self._running = True
        self._extracted_files.clear()
        self._target_dir_preexisted = os.path.exists(target_dir)

        self._install_thread = threading.Thread(
            target=self._run_installation,
            args=(archive_path, target_dir, selected_tasks),
            daemon=True,
        )
        self._install_thread.start()

    def request_cancel(self):
        """Signal the installation thread to stop as soon as possible."""
        self._running = False

    def wait_for_thread(self, timeout: float = 5.0):
        """Block until the installation thread finishes (or timeout)."""
        if self._install_thread and self._install_thread.is_alive():
            self._install_thread.join(timeout=timeout)

    def perform_rollback(self, target_dir: str):
        """
        Remove everything we created, in order.
        Calls self.on_rollback_step(msg) and self.on_rollback_finished().
        """
        cleanup_tasks: list = []

        if self.data.application_executable_path:
            p = self.data.application_executable_path
            cleanup_tasks.append(
                (_("Removing executable symlink..."), lambda path=p: self._safe_remove(path))
            )

        if self.data.application_icon_path:
            p = self.data.application_icon_path
            cleanup_tasks.append(
                (_("Removing icon symlink..."), lambda path=p: self._safe_remove(path))
            )

        if self.data.application_desktop_path:
            if self.data.application_desktop_source:
                p = os.path.join(self.data.application_desktop_path, self.data.application_desktop_source)
                cleanup_tasks.append(
                    (_("Removing desktop file..."), lambda path=p: self._safe_remove(path))
                )
            u_desktop = os.path.join(self.data.application_desktop_path, f"{self.data.application_name_slug}-uninstaller.desktop")
            cleanup_tasks.append(
                (_("Removing uninstaller desktop file..."), lambda path=u_desktop: self._safe_remove(path))
            )

        if self.data.application_executable_path:
            u_bin = os.path.join(os.path.dirname(self.data.application_executable_path), f"{self.data.application_name_slug}-uninstaller")
            cleanup_tasks.append(
                (_("Removing uninstaller..."), lambda path=u_bin: self._safe_remove(path))
            )

        if getattr(self.data, 'application_uninstaller_icon_path', None):
            cleanup_tasks.append(
                (_("Removing uninstaller icon..."), lambda path=self.data.application_uninstaller_icon_path: self._safe_remove(path))
            )

        if self._target_dir_preexisted:
            cleanup_tasks.append(
                (_("Cleaning up extracted files..."), self._remove_extracted_files)
            )
        else:
            cleanup_tasks.append(
                (_("Removing installation directory..."), lambda: self._safe_rmtree(target_dir))
            )

        for text, func in cleanup_tasks:
            if self.on_rollback_step:
                self.on_rollback_step(text)
            try:
                func()
            except Exception:
                pass

        if self.on_rollback_finished:
            self.on_rollback_finished()

    def _run_installation(self, archive_path: str, target_dir: str,
                          selected_tasks: List[AdditionalTask]):
        """Internal method to execute the full installation sequence."""
        try:
            if self.data.application_pre_installation_script and self._running:
                self._execute_command(
                    self.data.application_pre_installation_script,
                    _("Pre-Installation script"),
                    cwd=BASE_DIR,
                    abort_on_fail=True,
                )

            if self._running:
                decompress(
                    archive_path,
                    target_dir,
                    self.data.application_compression_type,
                    callback=self._decompression_callback,
                )

            if self._running:
                self._finalize_installation(target_dir)

            if self.data.application_post_installation_script and self._running:
                self._execute_command(
                    self.data.application_post_installation_script,
                    _("Post-Installation script"),
                    cwd=target_dir,
                    abort_on_fail=True,
                )

            if self._running:
                self._run_additional_tasks(target_dir, selected_tasks)

            if self._running:
                self._create_language_file(target_dir)

            if self._running:
                if is_root():
                    fix_ownership(target_dir)
                    if self.data.application_executable_path:
                        exe_link = os.path.join(self.data.application_executable_path, self.data.application_name_slug)
                        fix_ownership(exe_link)
                        uninst_bin = os.path.join(self.data.application_executable_path, f"{self.data.application_name_slug}-uninstaller")
                        fix_ownership(uninst_bin)
                    if self.data.application_desktop_path:
                        if self.data.application_desktop_source:
                            desktop_file = os.path.join(self.data.application_desktop_path, self.data.application_desktop_source)
                            fix_ownership(desktop_file)
                        u_desktop = os.path.join(self.data.application_desktop_path, f"{self.data.application_name_slug}-uninstaller.desktop")
                        fix_ownership(u_desktop)
                    if self.data.application_icon_path and self.data.application_icon_source:
                        icon_file = os.path.join(self.data.application_icon_path, self.data.application_icon_source)
                        fix_ownership(icon_file)
                    if getattr(self.data, 'application_uninstaller_icon_path', None):
                        fix_ownership(self.data.application_uninstaller_icon_path)

                if self.on_finished:
                    self.on_finished()

        except Exception as e:
            if self.on_error:
                self.on_error(str(e))

    def _decompression_callback(self, current: int, total: int, filename: str):
        """Callback to update progress and track extracted files during decompression."""
        full_path = os.path.join(self.data.application_installation_path, filename)
        if full_path not in self._extracted_files:
            self._extracted_files[full_path] = None

        percent = (current / total) * 100
        if self.on_progress:
            self.on_progress(percent, filename)

    def _execute_command(self, cmd_path: str, label: str, cwd: str | None = None,
                         abort_on_fail: bool = True):
        """Run a script or command with subprocess."""
        if self.on_status:
            self.on_status(_("Running {}...").format(label))

        parts = shlex.split(cmd_path)
        if not parts:
            return

        exe = parts[0]
        args = parts[1:]

        if not os.path.isabs(exe):
            bundled_path = os.path.join(BASE_DIR, exe)
            if os.path.exists(bundled_path):
                exe = bundled_path
                try:
                    os.chmod(exe, 0o755)
                except Exception:
                    pass
            else:
                potential_path = os.path.join(cwd if cwd else os.getcwd(), exe)
                if os.path.exists(potential_path):
                    exe = potential_path
                    try:
                        os.chmod(exe, 0o755)
                    except Exception:
                        pass

        cmd_list = [exe] + args
        
        if exe.endswith('.sh') and os.path.exists(exe):
            cmd_list = ["/bin/sh"] + cmd_list

        try:
            result = subprocess.run(
                cmd_list, shell=False, cwd=cwd, capture_output=True, text=True,
            )
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else _(
                    "Exit code {}").format(result.returncode)
                if abort_on_fail:
                    raise RuntimeError(_("{} failed: {}").format(label, error_msg))
                else:
                    if self.on_task_warning:
                        self.on_task_warning(
                            _("Task Warning"),
                            _("{} completed with errors:\n\n{}").format(label, error_msg),
                        )
        except Exception:
            if abort_on_fail:
                raise

    def _run_additional_tasks(self, target_dir: str, selected_tasks: List[AdditionalTask]):
        """Runs tasks selected by the user in AdditionalTasksPage."""
        for task in selected_tasks:
            if not self._running:
                break
            self._execute_command(task.command, task.name, cwd=target_dir, abort_on_fail=False)

    def _finalize_installation(self, target_dir: str):
        """Creates symlinks and moves desktop files based on config."""
        if self.data.application_executable_path and self.data.application_executable_source:
            src = os.path.join(target_dir, self.data.application_executable_source)
            dst = self.data.application_executable_path
            self._create_safe_symlink(src, dst, _("executable"))

        if not self._running:
            return

        if self.data.application_icon_path and self.data.application_icon_source:
            src = os.path.join(target_dir, self.data.application_icon_source)
            dst = self.data.application_icon_path
            self._create_safe_symlink(src, dst, _("icon"))

        if not self._running:
            return

        if self.data.application_desktop_path and self.data.application_desktop_source:
            src = os.path.join(target_dir, self.data.application_desktop_source)
            dst_dir = self.data.application_desktop_path
            if os.path.exists(src):
                try:
                    os.makedirs(dst_dir, exist_ok=True)
                    dst = os.path.join(dst_dir, os.path.basename(src))
                    if os.path.lexists(dst):
                        os.remove(dst)
                    shutil.move(src, dst)
                    if self.on_status:
                        self.on_status(_("Deployed desktop file..."))
                except Exception:
                    pass

        if self.data.application_desktop_path:
            u_src = os.path.join(target_dir, f"{self.data.application_name_slug}-uninstaller.desktop")
            if os.path.exists(u_src):
                try:
                    os.makedirs(self.data.application_desktop_path, exist_ok=True)
                    dst = os.path.join(self.data.application_desktop_path, os.path.basename(u_src))
                    if os.path.lexists(dst):
                        os.remove(dst)
                    shutil.move(u_src, dst)
                    if self.on_status:
                        self.on_status(_("Deployed uninstaller desktop file..."))
                except Exception:
                    pass
        
        if self.data.application_executable_path:
            u_bin = os.path.join(target_dir, f"{self.data.application_name_slug}-uninstaller")
            if os.path.exists(u_bin):
                try:
                    dst_dir = os.path.dirname(self.data.application_executable_path)
                    os.makedirs(dst_dir, exist_ok=True)
                    dst = os.path.join(dst_dir, f"{self.data.application_name_slug}-uninstaller")
                    if os.path.lexists(dst):
                        os.remove(dst)
                    shutil.move(u_bin, dst)
                    os.chmod(dst, 0o755)
                    if self.on_status:
                        self.on_status(_("Deployed uninstaller..."))
                except Exception:
                    pass

        if getattr(self.data, 'application_uninstaller_icon_path', None):
            _base, ext = os.path.splitext(self.data.application_uninstaller_icon_path)
            u_icon_src = os.path.join(target_dir, f"{self.data.application_name_slug}-uninstaller{ext}")
            
            if os.path.exists(u_icon_src):
                try:
                    dst_dir = os.path.dirname(self.data.application_uninstaller_icon_path)
                    os.makedirs(dst_dir, exist_ok=True)
                    dst = self.data.application_uninstaller_icon_path
                    if os.path.lexists(dst):
                        os.remove(dst)
                    shutil.move(u_icon_src, dst)
                    if self.on_status:
                        self.on_status(_("Deployed uninstaller icon..."))
                except Exception:
                    pass

    def _create_safe_symlink(self, src: str, dst: str, label: str):
        """Helper to create a symlink, removing existing files if necessary."""
        if not os.path.exists(src):
            if self.on_error:
                self.on_error(_("Failed to create {} symlink: source file does not exist.").format(label))
            raise Exception("Symlink source not found")

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.lexists(dst):
                os.remove(dst)
            os.symlink(src, dst)
            if self.on_status:
                self.on_status(_("Created {} symlink...").format(label))
        except Exception as e:
            if self.on_error:
                self.on_error(_("Failed to create {} symlink: {}").format(label, str(e)))
            raise

    def _create_language_file(self, target_dir: str):
        """Create the language detection file for the uninstaller."""
        try:
            lang_file_path = os.path.join(target_dir, self.data.current_lang)
            with open(lang_file_path, "w", encoding="utf-8"):
                pass
        except Exception:
            pass

    def _safe_remove(self, path: str):
        """Safely remove a file or symlink."""
        if os.path.lexists(path):
            os.remove(path)

    def _safe_rmtree(self, path: str):
        """Safely remove a directory tree."""
        if os.path.exists(path) and os.path.isdir(path):
            shutil.rmtree(path)

    def _remove_extracted_files(self):
        """Only remove files that were tracked during decompression."""
        for path in reversed(self.extracted_files):
            if os.path.isfile(path) or os.path.islink(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
            elif os.path.isdir(path):
                try:
                    os.rmdir(path)
                except Exception:
                    pass
