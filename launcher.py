"""
PokeBANK Launcher with system tray icon and update checker.
"""

import json
import threading
import webbrowser
import urllib.request
import tkinter as tk
from tkinter import messagebox

VERSION = "2.0.0"
GITHUB_RELEASES_API = "https://api.github.com/repos/Zero-Hex/Poke-Bank-Unbound/releases/latest"

try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

server_running = False


def run_server():
    global server_running
    if server_running:
        return
    server_running = True
    try:
        from app import app
        try:
            from waitress import serve
            serve(app, host="127.0.0.1", port=5000, threads=16)
        except ImportError:
            app.run(debug=False, port=5000, threaded=True)
    except Exception as e:
        messagebox.showerror("Server Error", f"Failed to start server:\n{e}")


def launch_bank(root):
    threading.Thread(target=run_server, daemon=True).start()
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5000")).start()
    messagebox.showinfo("Unbound Bank", "Starting Unbound Bank...\nYour browser will open shortly.")


def check_for_updates():
    def do_check():
        try:
            req = urllib.request.Request(
                GITHUB_RELEASES_API,
                headers={"User-Agent": "UnboundBank", "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read())

            if data.get("prerelease"):
                messagebox.showinfo("Update Check", f"v{VERSION}\n\n✓ You are up to date!")
                return

            latest_tag = data.get("tag_name", "").lstrip("v")
            release_url = data.get("html_url", "")

            def parse_ver(v):
                try:
                    return tuple(int(x) for x in v.lstrip("v").split("."))
                except Exception:
                    return (0, 0, 0)

            if parse_ver(VERSION) >= parse_ver(latest_tag):
                messagebox.showinfo("Update Check", f"v{VERSION}\n\n✓ You are up to date!")
            else:
                answer = messagebox.askyesno(
                    "Update Available",
                    f"Current: v{VERSION}\nLatest:  v{latest_tag}\n\nOpen release page?",
                )
                if answer:
                    webbrowser.open(release_url)

        except urllib.error.URLError as e:
            messagebox.showerror("Update Check Failed", f"Could not reach GitHub:\n{e.reason}")
        except Exception as e:
            messagebox.showerror("Update Check Failed", f"Error:\n{e}")

    threading.Thread(target=do_check, daemon=True).start()


def make_tray_icon():
    try:
        import os
        hoopa_path = os.path.join(os.path.dirname(__file__), "static/sprites/gFrontSprite828Hoopa.png")
        if os.path.exists(hoopa_path):
            img = Image.open(hoopa_path).convert("RGBA")
            # Resize to 64x64 if needed and add a background
            if img.size != (64, 64):
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
            return img
    except Exception:
        pass
    # Fallback: create a simple "UB" icon if Hoopa sprite not found
    img = Image.new("RGB", (64, 64), "#1e293b")
    draw = ImageDraw.Draw(img)
    draw.ellipse([6, 6, 58, 58], fill="#0284c7", outline="#60a5fa", width=3)
    draw.text((16, 20), "UB", fill="white")
    return img


def main():
    root = tk.Tk()
    root.title("Unbound Bank")
    root.geometry("350x420")
    root.resizable(False, False)
    root.configure(bg="#0f172a")

    # Set window icon to Hoopa
    try:
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "hoopa_icon.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass

    # Centre on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 350) // 2
    y = (root.winfo_screenheight() - 420) // 2
    root.geometry(f"350x420+{x}+{y}")

    tk.Label(root, text="UNBOUNDBANK", font=("Helvetica", 15, "bold"),
             bg="#0f172a", fg="#0284c7").pack(pady=(18, 2))
    tk.Label(root, text=f"v{VERSION}", font=("Helvetica", 8),
             bg="#0f172a", fg="#64748b").pack(pady=(0, 12))

    # Display Hoopa sprite
    try:
        import os
        hoopa_path = os.path.join(os.path.dirname(__file__), "static/sprites/gFrontSprite828Hoopa.png")
        if os.path.exists(hoopa_path) and HAS_TRAY:  # Only if PIL is available
            hoopa_pil = Image.open(hoopa_path).convert("RGBA")
            hoopa_pil = hoopa_pil.resize((150, 150), Image.Resampling.LANCZOS)
            hoopa_photoimg = ImageTk.PhotoImage(hoopa_pil)
            img_label = tk.Label(root, image=hoopa_photoimg, bg="#0f172a")
            img_label.image = hoopa_photoimg  # Keep a reference to prevent garbage collection
            img_label.pack(pady=8)
    except Exception:
        pass

    btn_style = dict(font=("Helvetica", 10, "bold"), relief=tk.FLAT,
                     cursor="hand2", bd=0, pady=8)

    tk.Button(root, text="Start Unbound Bank", bg="#0284c7", fg="white",
              command=lambda: launch_bank(root),
              **btn_style).pack(fill=tk.X, padx=20, pady=(0, 6))

    tk.Button(root, text="Check for Updates", bg="#334155", fg="white",
              command=check_for_updates,
              **btn_style).pack(fill=tk.X, padx=20, pady=(0, 6))

    if HAS_TRAY:
        tray_icon = None

        def show_window(icon=None, item=None):
            root.after(0, root.deiconify)
            root.after(0, root.lift)

        def exit_app(icon=None, item=None):
            if tray_icon:
                tray_icon.stop()
            root.after(0, root.destroy)

        def hide_to_tray():
            root.withdraw()

        menu = pystray.Menu(
            pystray.MenuItem("Show", show_window, default=True),
            pystray.MenuItem("Exit", exit_app),
        )
        tray_icon = pystray.Icon("PokeBANK", make_tray_icon(), menu=menu, title="Unbound Bank")

        root.protocol("WM_DELETE_WINDOW", hide_to_tray)
        threading.Thread(target=tray_icon.run, daemon=True).start()

        tk.Button(root, text="Exit", bg="#1e293b", fg="#94a3b8",
                  command=exit_app,
                  **btn_style).pack(fill=tk.X, padx=20)
    else:
        tk.Label(root, text="⚠ pystray/Pillow not installed\nTray icon unavailable",
                 font=("Helvetica", 7), bg="#0f172a", fg="#f59e0b",
                 justify=tk.CENTER).pack(pady=(6, 0))
        tk.Button(root, text="Exit", bg="#1e293b", fg="#94a3b8",
                  command=root.destroy,
                  **btn_style).pack(fill=tk.X, padx=20)
        root.protocol("WM_DELETE_WINDOW", root.destroy)

    root.mainloop()


if __name__ == "__main__":
    main()
