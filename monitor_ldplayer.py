import time
import psutil
import winreg
import pyautogui
import traceback
import ctypes
import os

# precisa do pywin32:
import win32gui
import win32con
import win32process

PROCESS_NAME = "dnplayer.exe"
REG_PATH = r"Control Panel\\Desktop"

os.startfile("D:\\LDPlayer\\LDPlayer4.0\\dnplayer.exe")
print("Aguardando LDPlayer iniciar....")
time.sleep(40)
print("Iniciando...")

# --- Funções de protetor de tela ---
def get_screensaver_config():
    config = {}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH) as key:
        for name in ["ScreenSaveActive", "SCRNSAVE.EXE", "ScreenSaveTimeOut"]:
            try:
                value, _ = winreg.QueryValueEx(key, name)
                config[name] = value
            except FileNotFoundError:
                config[name] = None
    return config

def disable_screensaver():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "ScreenSaveActive", 0, winreg.REG_SZ, "0")
        winreg.SetValueEx(key, "SCRNSAVE.EXE", 0, winreg.REG_SZ, "")

def restore_screensaver(config):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
        for k, v in config.items():
            if v is not None:
                winreg.SetValueEx(key, k, 0, winreg.REG_SZ, str(v))

def is_process_running(name: str):
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] and proc.info["name"].lower() == name.lower():
            return True
    return False

# --- Manipulação de janelas ---
def _get_dnplayer_pids():
    pids = []
    for p in psutil.process_iter(["name", "pid"]):
        if p.info["name"] and p.info["name"].lower() == PROCESS_NAME.lower():
            pids.append(p.info["pid"])
    return pids

def find_ldplayer_hwnd():
    """Procura janelas do LDPlayer pelo PID ou pelo título."""
    pids = _get_dnplayer_pids()
    candidates = []

    def enum_callback(hwnd, extra):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd) or ""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return
        if pid in pids or "ldplayer" in title.lower():
            extra.append((hwnd, title, pid))

    win32gui.EnumWindows(enum_callback, candidates)
    if not candidates:
        return None
    hwnd, title, pid = candidates[-1]  # pega a última encontrada
    return hwnd

def force_foreground(hwnd, max_retries=3, wait=0.3):
    """Força uma janela ao foreground usando múltiplas tentativas."""
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        for _ in range(max_retries):
            try:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(wait)
                if win32gui.GetForegroundWindow() == hwnd:
                    return True
            except Exception:
                pass

            # Tentativa avançada com AttachThreadInput
            fg = win32gui.GetForegroundWindow()
            if fg:
                fg_tid, _ = win32process.GetWindowThreadProcessId(fg)
                tgt_tid, _ = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    ctypes.windll.user32.AttachThreadInput(fg_tid, tgt_tid, True)
                    win32gui.SetForegroundWindow(hwnd)
                finally:
                    ctypes.windll.user32.AttachThreadInput(fg_tid, tgt_tid, False)

            time.sleep(wait)

        return win32gui.GetForegroundWindow() == hwnd
    except Exception as e:
        print("Erro em force_foreground:", e)
        traceback.print_exc()
        return False

def bring_ldplayer_to_front(retries=5, delay_between=0.6):
    """Tenta várias vezes trazer LDPlayer para frente."""
    for _ in range(retries):
        hwnd = find_ldplayer_hwnd()
        if hwnd:
            if force_foreground(hwnd):
                return True
        time.sleep(delay_between)
    return False

def send_f11():
    pyautogui.press("f11")

# --- Loop principal ---
def main():
    print("🔍 Monitorando LDPlayer... (Ctrl+C para sair)")
    original_config = get_screensaver_config()
    screensaver_disabled = False
    f11_sent = False

    try:
        while True:
            if is_process_running(PROCESS_NAME):
                if not screensaver_disabled:
                    print("⚡ LDPlayer em execução → Desligando o Protetor de Tela")
                    disable_screensaver()
                    screensaver_disabled = True
                    f11_sent = False

                if not f11_sent:
                    print("🎮 Tentando focar LDPlayer...")
                    time.sleep(3)  # espera abrir janela
                    if bring_ldplayer_to_front():
                        print("✅ Maximizando tela do LDPlayer.")
                        send_f11()
                    else:
                        print("❌ LDPlayer não localizado → Tentando enviar F11 mesmo assim.")
                        send_f11()
                    f11_sent = True
            else:
                if screensaver_disabled:
                    print("✅ LDPlayer fechado → Restaurando Protetor de Tela...")
                    restore_screensaver(original_config)
                    print("⏹ Encerrando...")
                    break  # encerra o script
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n⏹ Encerrando manualmente...")
        restore_screensaver(original_config)
        print("🔄 Protetor de Tela restaurado.")

if __name__ == "__main__":
    main()
