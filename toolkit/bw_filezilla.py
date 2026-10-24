"""BeardedWolf Admin: bezpieczny lokalny odczyt metadanych eksportu FileZilli.

Nigdy nie czyta wartości Pass jako poświadczeń, nie dekoduje Base64,
nie kopiuje XML, nie zapisuje haseł i nie wykonuje połączeń sieciowych.
"""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

MAX_XML_BYTES = 5 * 1024 * 1024
# FileZilla: 0 FTP, 1 SFTP, 3/4 FTP/TLS w znanych formatach eksportu.
PROTOCOLS = {"0": "ftp", "1": "sftp", "3": "ftps", "4": "ftps"}


def _value(element, tag):
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def read_export(path):
    """Zwraca wyłącznie metadane (bez hasła i pól uwierzytelniających)."""
    file = Path(path)
    if not file.is_file():
        raise ValueError("Wskaż lokalny plik eksportu XML z FileZilli.")
    if file.stat().st_size > MAX_XML_BYTES:
        raise ValueError("Plik jest za duży, ograniczenie 5 MiB.")
    raw = file.read_bytes()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Odrzucono XML z definicją DTD/ENTITY.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("Nieprawidłowy lub niepełny plik XML FileZilli.") from exc
    if root.tag != "FileZilla3":
        raise ValueError("To nie jest standardowy eksport FileZilla3.")
    servers_root = root.find("Servers")
    if servers_root is None:
        raise ValueError("W eksporcie brakuje sekcji Servers.")
    result = []
    # Również zagnieżdżone katalogi zakładek z Menedżera stron.
    for node in servers_root.iter("Server"):
        host = _value(node, "Host")
        port_raw = _value(node, "Port")
        username = _value(node, "User")
        label = _value(node, "Name") or (node.text or "").strip() or host
        protocol_raw = _value(node, "Protocol")
        # Hasła i Logontype ani pola Account/Keyfile celowo nie są pobierane.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]{0,252}", host):
            continue
        try:
            port = int(port_raw) if port_raw else (22 if protocol_raw == "1" else 21)
        except ValueError:
            continue
        if not 1 <= port <= 65535:
            continue
        access = PROTOCOLS.get(protocol_raw, "unknown")
        # Niejednoznaczne metody szyfrowania oznaczamy bez dopowiadania.
        result.append({
            "name": label[:100],
            "host": host,
            "port": port,
            "user": username[:90],
            "access": access,
            "protocol_code": protocol_raw,
        })
    return result
