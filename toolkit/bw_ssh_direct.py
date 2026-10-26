"""Test one authorized SSH/SFTP endpoint directly by host, login and port.

No alias lookup, no password capture, no key export, no brute force.
A successful remote 'exit' means public-key login worked AND shell commands
are permitted. A failure is not proof of invalid credentials.
"""
import os
import re
import shutil
import subprocess


def test_direct(host, user, port, timeout=8):
    host, user = str(host).strip(), str(user).strip()
    port = int(port)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]{0,252}", host):
        raise ValueError("Nieprawidlowy host SSH.")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]{0,89}", user):
        raise ValueError("Nieprawidlowy login SSH.")
    if not 1 <= port <= 65535:
        raise ValueError("Nieprawidlowy port.")
    ssh = shutil.which("ssh.exe")
    if not ssh:
        ssh = "/mnt/c/Windows/System32/OpenSSH/ssh.exe"
        if not os.path.isfile(ssh):
            raise RuntimeError("Brak Windows ssh.exe. Sprawdz instalacje klienta SSH.")

    # OpenSSH '-F none' disables user and system config files: no Host aliases.
    # Only default Windows keys and its ssh-agent will be tried.
    args = [ssh, "-F", "none",
            "-o", "BatchMode=yes",
            "-o", "NumberOfPasswordPrompts=0",
            "-o", "PreferredAuthentications=publickey",
            "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=" + str(max(3, min(12, timeout))),
            "-p", str(port), "-l", user, host, "exit"]
    try:
        result = subprocess.run(args, text=True, capture_output=True,
                                timeout=max(16, timeout+6), check=False)
    except subprocess.TimeoutExpired:
        return ("TIMEOUT", "Przekroczono limit czasu polaczenia.")
    error = (result.stderr or result.stdout or "").strip()
    # No raw stderr: banners may contain arbitrary remote data.
    if result.returncode == 0:
        return ("OK", "Dziala bezposrednie logowanie kluczem SSH Windows.")
    msg = error.lower()
    if "permission denied" in msg or "publickey" in msg:
        return ("AUTH_NEEDED", "Serwer odpowiada, ale obecne klucze Windows nie uwierzytelnily sesji. Haslo mogloby dzialac.")
    if "host key verification failed" in msg:
        return ("HOST_KEY", "Klucz hosta nie jest zaufany w Windows. Porownaj odcisk poza tym polaczeniem.")
    if "could not resolve" in msg:
        return ("DNS", "Nie udalo sie rozpoznac nazwy hosta.")
    if "connection refused" in msg:
        return ("REFUSED", "Port SSH odrzuca polaczenie.")
    if "timed out" in msg or "connection timed out" in msg:
        return ("TIMEOUT", "Host lub port nie odpowiada w limicie.")
    return ("CHECK", "Brak potwierdzenia logowania; mozliwa ograniczona powloka lub inna metoda uwierzytelnienia (kod %s)." % result.returncode)
