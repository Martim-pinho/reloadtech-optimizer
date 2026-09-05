"""Diagnóstico do sistema. Módulo estritamente de leitura — nunca altera nada."""
from __future__ import annotations

import json
import os
import platform
import re
import socket
from datetime import datetime, timedelta

import psutil

from ..platform_info import (
    IS_LINUX,
    IS_MACOS,
    IS_WINDOWS,
    human_bytes,
    powershell_json,
    run,
)

UNKNOWN = "n/d"


# --- Sistema -----------------------------------------------------------------

def _macos_hardware() -> dict:
    result = run(["system_profiler", "SPHardwareDataType", "-json"], timeout=25)
    if not result.ok:
        return {}
    try:
        items = json.loads(result.out).get("SPHardwareDataType", [])
    except json.JSONDecodeError:
        return {}
    return items[0] if items else {}


def _linux_os_release() -> dict:
    values: dict[str, str] = {}
    try:
        with open("/etc/os-release", encoding="utf-8") as handle:
            for line in handle:
                key, _, value = line.strip().partition("=")
                if key:
                    values[key] = value.strip('"')
    except OSError:
        pass
    return values


def _dmi(name: str) -> str:
    """Lê /sys/class/dmi/id/<name>. Alguns campos exigem root."""
    try:
        with open(f"/sys/class/dmi/id/{name}", encoding="utf-8") as handle:
            value = handle.read().strip()
        return value or UNKNOWN
    except OSError:
        return UNKNOWN


def is_server() -> bool:
    """Deteta ambientes sem interface gráfica (servidores, contentores, SSH)."""
    if IS_WINDOWS:
        data = powershell_json("Get-CimInstance Win32_OperatingSystem | Select-Object ProductType")
        if isinstance(data, dict):
            return data.get("ProductType") in (2, 3)
        return False
    if IS_MACOS:
        return False
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return False
    return True


def _macos_version() -> str:
    result = run(["sw_vers", "-productVersion"])
    name = run(["sw_vers", "-productName"])
    if result.ok:
        return f"{name.out if name.ok else 'macOS'} {result.out}"
    return platform.platform()


def system_overview() -> dict:
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot
    info = {
        "hostname": socket.gethostname(),
        "utilizador": psutil.Process().username(),
        "sistema": UNKNOWN,
        "modelo": UNKNOWN,
        "numero_serie": UNKNOWN,
        "arranque": boot.strftime("%d/%m/%Y %H:%M"),
        "tempo_ligado": _format_uptime(uptime),
        "arquitetura": platform.machine(),
    }

    if IS_WINDOWS:
        data = powershell_json(
            "Get-CimInstance Win32_OperatingSystem | "
            "Select-Object Caption,Version,BuildNumber,OSArchitecture"
        )
        if isinstance(data, dict):
            info["sistema"] = f"{data.get('Caption', 'Windows')} (build {data.get('BuildNumber', UNKNOWN)})"
        else:
            info["sistema"] = platform.platform()
        cs = powershell_json("Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model")
        if isinstance(cs, dict):
            info["modelo"] = f"{cs.get('Manufacturer', '')} {cs.get('Model', '')}".strip() or UNKNOWN
        bios = powershell_json("Get-CimInstance Win32_BIOS | Select-Object SerialNumber")
        if isinstance(bios, dict):
            info["numero_serie"] = str(bios.get("SerialNumber") or UNKNOWN).strip()
    elif IS_MACOS:
        info["sistema"] = _macos_version()
        hardware = _macos_hardware()
        info["modelo"] = hardware.get("machine_name") or hardware.get("machine_model") or UNKNOWN
        info["numero_serie"] = hardware.get("serial_number") or UNKNOWN
    elif IS_LINUX:
        release = _linux_os_release()
        kernel = platform.release()
        info["sistema"] = f"{release.get('PRETTY_NAME', 'Linux')} (kernel {kernel})"
        vendor = _dmi("sys_vendor")
        product = _dmi("product_name")
        modelo = " ".join(part for part in (vendor, product) if part != UNKNOWN)
        info["modelo"] = modelo or UNKNOWN
        info["numero_serie"] = _dmi("product_serial")
        info["servidor"] = is_server()
        carga = os.getloadavg()
        info["carga_media"] = f"{carga[0]:.2f} / {carga[1]:.2f} / {carga[2]:.2f}".replace(".", ",")
    else:
        info["sistema"] = platform.platform()

    return info


def _format_uptime(delta: timedelta) -> str:
    days = delta.days
    hours, rest = divmod(delta.seconds, 3600)
    minutes = rest // 60
    parts = []
    if days:
        parts.append(f"{days} dia{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}min")
    return " ".join(parts)


# --- CPU ---------------------------------------------------------------------

def cpu_info() -> dict:
    name = platform.processor() or UNKNOWN
    if IS_WINDOWS:
        data = powershell_json("Get-CimInstance Win32_Processor | Select-Object Name,MaxClockSpeed")
        if isinstance(data, list):
            data = data[0] if data else None
        if isinstance(data, dict):
            name = str(data.get("Name") or name).strip()
    elif IS_MACOS:
        hardware = _macos_hardware()
        name = hardware.get("chip_type") or hardware.get("cpu_type") or name
        if name == UNKNOWN:
            result = run(["sysctl", "-n", "machdep.cpu.brand_string"])
            if result.ok:
                name = result.out
    elif IS_LINUX:
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.lower().startswith(("model name", "hardware")):
                        name = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass

    freq = psutil.cpu_freq()
    return {
        "modelo": name,
        "nucleos_fisicos": psutil.cpu_count(logical=False) or UNKNOWN,
        "nucleos_logicos": psutil.cpu_count(logical=True) or UNKNOWN,
        "frequencia": f"{freq.current / 1000:.2f} GHz".replace(".", ",") if freq and freq.current else UNKNOWN,
        "utilizacao_pct": psutil.cpu_percent(interval=0.6),
    }


# --- Memória -----------------------------------------------------------------

def memory_info() -> dict:
    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total": virtual.total,
        "usada": virtual.used,
        "disponivel": virtual.available,
        "utilizacao_pct": virtual.percent,
        "total_legivel": human_bytes(virtual.total),
        "usada_legivel": human_bytes(virtual.used),
        "disponivel_legivel": human_bytes(virtual.available),
        "swap_usada_legivel": human_bytes(swap.used),
        "swap_pct": swap.percent,
    }


# --- Discos ------------------------------------------------------------------

# Sistemas de ficheiros que não representam armazenamento real do utilizador
_FS_IGNORADOS = {"squashfs", "overlay", "tmpfs", "devtmpfs", "autofs", "devfs", "proc", "sysfs"}


def _partition_relevante(part) -> bool:
    """Filtra volumes que não interessam ao cliente.

    Sem isto, um Mac apresenta as imagens de disco dos instaladores (Discord,
    VS Code…) como "discos a 99%", e o Linux mostra dezenas de montagens snap.
    """
    opcoes = part.opts.lower()
    if part.fstype.lower() in _FS_IGNORADOS:
        return False
    if "read-only" in opcoes or opcoes.split(",")[0] == "ro":
        return False  # imagens de disco e sistemas de ficheiros só de leitura

    if IS_WINDOWS:
        return "cdrom" not in opcoes
    if IS_MACOS:
        # O macOS divide o disco em volumes internos; só dois interessam.
        if part.mountpoint.startswith("/System/Volumes/"):
            return part.mountpoint == "/System/Volumes/Data"
        return part.mountpoint == "/" or part.mountpoint.startswith("/Volumes/")
    if IS_LINUX:
        ignorados = ("/snap/", "/var/lib/docker/", "/run/", "/sys/", "/proc/")
        return not part.mountpoint.startswith(ignorados)
    return True


def _nome_volume(part) -> str:
    if IS_MACOS:
        if part.mountpoint == "/System/Volumes/Data":
            return "Disco do sistema (dados)"
        if part.mountpoint == "/":
            return "Disco do sistema"
        return part.mountpoint.replace("/Volumes/", "")
    if part.mountpoint == "/":
        return "Raiz do sistema (/)"
    return part.mountpoint


def disk_partitions() -> list[dict]:
    partitions = []
    vistos: set[str] = set()

    for part in psutil.disk_partitions(all=False):
        if not _partition_relevante(part):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        if part.device in vistos:
            continue
        vistos.add(part.device)
        partitions.append(
            {
                "nome": _nome_volume(part),
                "dispositivo": part.device,
                "ponto_montagem": part.mountpoint,
                "sistema_ficheiros": part.fstype,
                "total": usage.total,
                "usado": usage.used,
                "livre": usage.free,
                "utilizacao_pct": usage.percent,
                "total_legivel": human_bytes(usage.total),
                "usado_legivel": human_bytes(usage.used),
                "livre_legivel": human_bytes(usage.free),
            }
        )

    # No macOS, "/" e o volume de dados partilham o mesmo contentor APFS:
    # mostrar os dois duplicaria a mesma capacidade no relatório.
    if IS_MACOS:
        dados = [p for p in partitions if p["ponto_montagem"] == "/System/Volumes/Data"]
        if dados:
            partitions = [p for p in partitions if p["ponto_montagem"] != "/"]

    return partitions


def physical_disks() -> list[dict]:
    """Estado de saúde dos discos físicos (SMART quando disponível)."""
    disks: list[dict] = []
    if IS_WINDOWS:
        data = powershell_json(
            "Get-PhysicalDisk | Select-Object FriendlyName,MediaType,HealthStatus,Size,SerialNumber"
        )
        if isinstance(data, dict):
            data = [data]
        for item in data or []:
            disks.append(
                {
                    "nome": item.get("FriendlyName") or UNKNOWN,
                    "tipo": item.get("MediaType") or UNKNOWN,
                    "saude": _translate_health(item.get("HealthStatus")),
                    "capacidade": human_bytes(item.get("Size") or 0),
                }
            )
    elif IS_MACOS:
        listing = run(["diskutil", "list", "-plist", "physical"], timeout=20)
        identifiers = re.findall(r"<string>(disk\d+)</string>", listing.out) if listing.ok else []
        for identifier in dict.fromkeys(identifiers):
            info = run(["diskutil", "info", identifier], timeout=15)
            if not info.ok:
                continue
            fields = dict(
                (key.strip(), value.strip())
                for key, _, value in (line.partition(":") for line in info.out.splitlines())
                if value.strip()
            )
            disks.append(
                {
                    "nome": fields.get("Device / Media Name", identifier),
                    "tipo": "SSD" if fields.get("Solid State") == "Yes" else fields.get("Protocol", UNKNOWN),
                    "saude": _translate_health(fields.get("SMART Status")),
                    "capacidade": fields.get("Disk Size", UNKNOWN).split("(")[0].strip() or UNKNOWN,
                }
            )
    elif IS_LINUX:
        listing = run(["lsblk", "-dJ", "-o", "NAME,MODEL,SIZE,ROTA,TYPE"], timeout=20)
        entries = []
        if listing.ok:
            try:
                entries = json.loads(listing.out).get("blockdevices", [])
            except json.JSONDecodeError:
                entries = []
        for entry in entries:
            if entry.get("type") != "disk":
                continue
            device = f"/dev/{entry.get('name')}"
            saude = UNKNOWN
            smart = run(["smartctl", "-H", device], timeout=20)
            if smart.code >= 0 and smart.out:
                match = re.search(r"(?:overall-health self-assessment test result|SMART Health Status):\s*(.+)", smart.out)
                if match:
                    saude = _translate_health(match.group(1).strip())
            disks.append(
                {
                    "nome": entry.get("model") or device,
                    "tipo": "HDD" if entry.get("rota") else "SSD/NVMe",
                    "saude": saude,
                    "capacidade": entry.get("size") or UNKNOWN,
                }
            )
    return disks


def _translate_health(value) -> str:
    mapping = {
        "healthy": "Saudável",
        "verified": "Saudável",
        "ok": "Saudável",
        "warning": "Atenção",
        "unhealthy": "Problema detetado",
        "failing": "A falhar — substituir",
        "not supported": "Não suportado",
        "passed": "Saudável",
        "failed!": "A falhar — substituir",
    }
    if value is None:
        return UNKNOWN
    return mapping.get(str(value).strip().lower(), str(value))


# --- GPU, bateria e temperaturas ---------------------------------------------

def gpu_info() -> list[str]:
    if IS_WINDOWS:
        data = powershell_json("Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion")
        if isinstance(data, dict):
            data = [data]
        return [
            f"{item.get('Name', UNKNOWN)} (driver {item.get('DriverVersion', UNKNOWN)})"
            for item in data or []
        ]
    if IS_MACOS:
        result = run(["system_profiler", "SPDisplaysDataType", "-json"], timeout=25)
        if result.ok:
            try:
                items = json.loads(result.out).get("SPDisplaysDataType", [])
                return [item.get("sppci_model", UNKNOWN) for item in items]
            except json.JSONDecodeError:
                pass
    elif IS_LINUX:
        result = run(["lspci"], timeout=15)
        if result.ok:
            return [
                line.split(":", 2)[-1].strip()
                for line in result.out.splitlines()
                if re.search(r"VGA compatible controller|3D controller", line)
            ]
    return []


def battery_info() -> dict | None:
    try:
        battery = psutil.sensors_battery()
    except Exception:  # noqa: BLE001
        return None
    if battery is None:
        return None
    health = UNKNOWN
    cycles = UNKNOWN
    if IS_MACOS:
        result = run(["system_profiler", "SPPowerDataType", "-json"], timeout=20)
        if result.ok:
            try:
                power = json.loads(result.out).get("SPPowerDataType", [])
                for entry in power:
                    health_info = entry.get("sppower_battery_health_info") or {}
                    if health_info:
                        cycles = health_info.get("sppower_battery_cycle_count", UNKNOWN)
                        health = health_info.get("sppower_battery_health", UNKNOWN)
            except json.JSONDecodeError:
                pass
    elif IS_WINDOWS:
        data = powershell_json("Get-CimInstance Win32_Battery | Select-Object DesignCapacity,FullChargeCapacity")
        if isinstance(data, dict) and data.get("DesignCapacity") and data.get("FullChargeCapacity"):
            ratio = data["FullChargeCapacity"] / data["DesignCapacity"] * 100
            health = f"{ratio:.0f}% da capacidade original"
    return {
        "percentagem": round(battery.percent),
        "ligado_corrente": battery.power_plugged,
        "saude": health,
        "ciclos": cycles,
    }


def temperatures() -> dict[str, float]:
    temps: dict[str, float] = {}
    getter = getattr(psutil, "sensors_temperatures", None)
    if getter:
        try:
            for name, entries in (getter() or {}).items():
                for entry in entries:
                    if entry.current:
                        temps[entry.label or name] = round(entry.current, 1)
        except Exception:  # noqa: BLE001
            pass
    if not temps and IS_WINDOWS:
        data = powershell_json(
            "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
            "-ErrorAction SilentlyContinue | Select-Object CurrentTemperature"
        )
        if isinstance(data, dict):
            data = [data]
        for index, item in enumerate(data or []):
            raw = item.get("CurrentTemperature")
            if raw:
                temps[f"Zona térmica {index + 1}"] = round(raw / 10 - 273.15, 1)
    return temps


# --- Processos ---------------------------------------------------------------

def top_processes(limit: int = 12) -> list[dict]:
    """Programas que mais recursos consomem agora."""
    processes = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            proc.cpu_percent(None)  # primeira leitura é sempre 0.0
            processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    psutil.cpu_percent(interval=0.8)

    rows = []
    cores = psutil.cpu_count(logical=True) or 1
    for proc in processes:
        try:
            info = proc.info
            rows.append(
                {
                    "pid": info["pid"],
                    "nome": info["name"] or UNKNOWN,
                    "cpu_pct": round(proc.cpu_percent(None) / cores, 1),
                    "memoria": info["memory_info"].rss if info["memory_info"] else 0,
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    rows.sort(key=lambda row: (row["cpu_pct"], row["memoria"]), reverse=True)
    for row in rows:
        row["memoria_legivel"] = human_bytes(row["memoria"])
    return rows[:limit]


# --- Avaliação e recolha completa --------------------------------------------

def build_findings(snapshot: dict) -> list[dict]:
    """Traduz os números em conclusões acionáveis para o técnico e para o cliente."""
    findings: list[dict] = []

    memory = snapshot.get("memoria", {})
    if memory.get("utilizacao_pct", 0) >= 85:
        findings.append(
            {
                "nivel": "alto",
                "titulo": "Memória RAM saturada",
                "detalhe": f"{memory['utilizacao_pct']:.0f}% da RAM em uso. "
                "O sistema está a recorrer ao disco, o que torna tudo mais lento.",
                "acao": "Fechar programas em segundo plano ou aumentar a RAM.",
            }
        )

    for partition in snapshot.get("particoes", []):
        if partition["utilizacao_pct"] >= 90:
            findings.append(
                {
                    "nivel": "alto",
                    "titulo": f"{partition.get('nome', partition['ponto_montagem'])} quase cheio",
                    "detalhe": f"{partition['utilizacao_pct']:.0f}% ocupado, "
                    f"apenas {partition['livre_legivel']} livres.",
                    "acao": "Executar a limpeza de ficheiros e arquivar dados antigos.",
                }
            )
        elif partition["utilizacao_pct"] >= 80:
            findings.append(
                {
                    "nivel": "medio",
                    "titulo": f"{partition.get('nome', partition['ponto_montagem'])} com pouco espaço",
                    "detalhe": f"{partition['utilizacao_pct']:.0f}% ocupado.",
                    "acao": "Recomenda-se limpeza preventiva.",
                }
            )

    for disk in snapshot.get("discos_fisicos", []):
        if disk["saude"] not in ("Saudável", UNKNOWN, "Não suportado"):
            findings.append(
                {
                    "nivel": "critico",
                    "titulo": f"Saúde do disco: {disk['nome']}",
                    "detalhe": f"Estado SMART reportado: {disk['saude']}.",
                    "acao": "Fazer cópia de segurança imediata e planear substituição do disco.",
                }
            )

    cpu = snapshot.get("cpu", {})
    if cpu.get("utilizacao_pct", 0) >= 85:
        findings.append(
            {
                "nivel": "medio",
                "titulo": "CPU sob carga elevada",
                "detalhe": f"Utilização de {cpu['utilizacao_pct']:.0f}% em repouso.",
                "acao": "Verificar a lista de processos e o que arranca com o sistema.",
            }
        )

    battery = snapshot.get("bateria")
    if battery and isinstance(battery.get("ciclos"), int) and battery["ciclos"] > 800:
        findings.append(
            {
                "nivel": "medio",
                "titulo": "Bateria com muitos ciclos",
                "detalhe": f"{battery['ciclos']} ciclos de carga registados.",
                "acao": "Autonomia reduzida é esperada; considerar substituição.",
            }
        )

    startup_count = snapshot.get("arranque_total")
    if isinstance(startup_count, int) and startup_count > 12:
        findings.append(
            {
                "nivel": "medio",
                "titulo": "Muitos programas a arrancar com o sistema",
                "detalhe": f"{startup_count} entradas de arranque detetadas.",
                "acao": "Desativar as que não são necessárias no separador Arranque.",
            }
        )

    if not findings:
        findings.append(
            {
                "nivel": "ok",
                "titulo": "Sem problemas relevantes detetados",
                "detalhe": "Os indicadores principais estão dentro dos valores normais.",
                "acao": "Manutenção preventiva periódica é suficiente.",
            }
        )
    return findings


def health_score(snapshot: dict) -> int:
    """Pontuação 0-100. Transparente: cada penalização vem de um valor medido."""
    score = 100
    memory = snapshot.get("memoria", {})
    score -= max(0, (memory.get("utilizacao_pct", 0) - 70)) * 0.5

    for partition in snapshot.get("particoes", []):
        score -= max(0, (partition["utilizacao_pct"] - 75)) * 0.6

    cpu = snapshot.get("cpu", {})
    score -= max(0, (cpu.get("utilizacao_pct", 0) - 70)) * 0.3

    for disk in snapshot.get("discos_fisicos", []):
        if disk["saude"] not in ("Saudável", UNKNOWN, "Não suportado"):
            score -= 35

    startup_count = snapshot.get("arranque_total")
    if isinstance(startup_count, int):
        score -= max(0, startup_count - 8) * 1.5

    return int(max(0, min(100, round(score))))


def collect(progress=None) -> dict:
    """Recolha completa. `progress(pct, texto)` é opcional."""

    def step(pct: int, text: str) -> None:
        if progress:
            progress(pct, text)

    step(5, "A identificar o sistema…")
    snapshot = {"gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"), "sistema": system_overview()}
    step(20, "A analisar o processador…")
    snapshot["cpu"] = cpu_info()
    step(35, "A analisar a memória…")
    snapshot["memoria"] = memory_info()
    step(50, "A analisar os discos…")
    snapshot["particoes"] = disk_partitions()
    snapshot["discos_fisicos"] = physical_disks()
    step(70, "A verificar gráficos, bateria e temperaturas…")
    snapshot["gpu"] = gpu_info()
    snapshot["bateria"] = battery_info()
    snapshot["temperaturas"] = temperatures()
    step(85, "A listar processos ativos…")
    snapshot["processos"] = top_processes()
    step(95, "A avaliar resultados…")
    snapshot["conclusoes"] = build_findings(snapshot)
    snapshot["pontuacao"] = health_score(snapshot)
    step(100, "Diagnóstico concluído")
    return snapshot
