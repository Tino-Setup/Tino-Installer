import sys
import os
import pwd
import shlex
from elevate import elevate

def is_root():
    """Checks if the current process has root privileges."""
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False

def get_original_user():
    """Returns the original username if running via sudo/pkexec, else None."""
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        return sudo_user
    pkexec_uid = os.environ.get("PKEXEC_UID")
    if pkexec_uid:
        try:
            return pwd.getpwuid(int(pkexec_uid)).pw_name
        except (ValueError, KeyError):
            pass
    return None

def needs_elevation(target_path):
    """Checks if the target path or its nearest existing parent requires elevation to write to."""
    if is_root():
        return False
    path = target_path
    while path and not os.path.exists(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return not os.access(path, os.W_OK)

def check_and_elevate(project_path=None):
    """
    Attempts to re-launch the current script with root privileges using the 'elevate' library.
    It uses graphical elevation (like pkexec or gksu) if available.
    """
    if not is_root():
        gui_env = {
            "DISPLAY": os.environ.get("DISPLAY", ""),
            "XAUTHORITY": os.environ.get("XAUTHORITY", ""),
            "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", "")
        }

        env_args = ["env"]
        for key, val in gui_env.items():
            if val:
                env_args.append(f"{key}={val}")

        old_exe = sys.executable
        sys.executable = "/usr/bin/env"
        
        args = sys.argv.copy()
        if project_path and project_path not in args:
            args.append(project_path)

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            sys.argv = env_args[1:] + [old_exe] + args[1:]
        else:
            sys.argv = env_args[1:] + [old_exe] + args

        elevate()

def drop_privileges_cmd(cmd):
    """
    Modifies a command list to drop privileges to the original user 
    if the app is running as root and an original user is detected.
    """
    if is_root():
        orig_user = get_original_user()
        if orig_user:
            return ["su", orig_user, "-c", shlex.join(cmd)]
    return cmd

def fix_ownership(path):
    """
    Recursively changes ownership of the given path back to the original user
    if the script is running as root and the parent directory is NOT owned by root.
    """
    if not is_root() or not path:
        return
        
    orig_user = get_original_user()
    if not orig_user:
        return
        
    parent_dir = os.path.dirname(os.path.abspath(path))
    if not parent_dir:
        parent_dir = "."
        
    try:
        parent_stat = os.stat(parent_dir)
        if parent_stat.st_uid == 0:
            return  # Parent is root-owned, so root ownership is expected for children
            
        user_info = pwd.getpwnam(orig_user)
        uid = user_info.pw_uid
        gid = user_info.pw_gid
        
        if os.path.isdir(path):
            for root_dir, dirs, files in os.walk(path):
                os.chown(root_dir, uid, gid)
                for item in dirs + files:
                    try:
                        os.chown(os.path.join(root_dir, item), uid, gid)
                    except OSError:
                        pass
        else:
            if os.path.exists(path):
                os.chown(path, uid, gid)
    except Exception:
        pass
