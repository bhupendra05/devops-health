"""Collect health metrics from a remote host via SSH."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

from devops_health.config import Host


@dataclass
class DiskInfo:
    mountpoint: str
    total_gb: float
    used_gb: float
    free_gb: float
    use_pct: float


@dataclass
class ProcessInfo:
    pid: int
    user: str
    cpu_pct: float
    mem_pct: float
    command: str


@dataclass
class HealthReport:
    host: str
    reachable: bool
    error: Optional[str] = None
    # System
    uptime_seconds: int = 0
    uptime_human: str = ""
    hostname: str = ""
    os_info: str = ""
    kernel: str = ""
    # CPU
    cpu_count: int = 0
    cpu_1m: float = 0.0
    cpu_5m: float = 0.0
    cpu_15m: float = 0.0
    cpu_pct: float = 0.0
    # Memory
    mem_total_gb: float = 0.0
    mem_used_gb: float = 0.0
    mem_free_gb: float = 0.0
    mem_pct: float = 0.0
    # Swap
    swap_total_gb: float = 0.0
    swap_used_gb: float = 0.0
    swap_pct: float = 0.0
    # Disk
    disks: List[DiskInfo] = field(default_factory=list)
    # Network
    rx_bytes: int = 0
    tx_bytes: int = 0
    # Processes
    top_processes: List[ProcessInfo] = field(default_factory=list)
    # Services
    services: dict = field(default_factory=dict)
    # Latency
    latency_ms: float = 0.0


def _run(conn, cmd: str) -> str:
    """Run a command over SSH and return stdout."""
    result = conn.run(cmd, hide=True, warn=True, timeout=10)
    return result.stdout.strip() if result.ok else ""


def collect(host: Host, check_services: List[str] | None = None) -> HealthReport:
    t0 = time.time()
    report = HealthReport(host=host.name, reachable=False)

    try:
        import fabric
    except ImportError:
        raise ImportError("Run: pip install fabric")

    try:
        conn = fabric.Connection(
            host=host.hostname,
            user=host.user,
            port=host.port,
            connect_kwargs=host.connect_kwargs,
            connect_timeout=10,
        )

        # Quick ping test
        conn.run("echo ok", hide=True, timeout=5)
        report.reachable = True
        report.latency_ms = (time.time() - t0) * 1000

        # Hostname + OS
        report.hostname = _run(conn, "hostname")
        report.os_info = _run(conn, "cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'")
        report.kernel = _run(conn, "uname -r")

        # Uptime
        uptime_raw = _run(conn, "cat /proc/uptime")
        if uptime_raw:
            secs = int(float(uptime_raw.split()[0]))
            report.uptime_seconds = secs
            d, rem = divmod(secs, 86400)
            h, rem = divmod(rem, 3600)
            m = rem // 60
            parts = []
            if d: parts.append(f"{d}d")
            if h: parts.append(f"{h}h")
            parts.append(f"{m}m")
            report.uptime_human = " ".join(parts)

        # CPU count
        cpu_raw = _run(conn, "nproc")
        report.cpu_count = int(cpu_raw) if cpu_raw.isdigit() else 0

        # Load average
        loadavg = _run(conn, "cat /proc/loadavg")
        if loadavg:
            parts = loadavg.split()
            report.cpu_1m = float(parts[0])
            report.cpu_5m = float(parts[1])
            report.cpu_15m = float(parts[2])
            if report.cpu_count:
                report.cpu_pct = min(100.0, (report.cpu_1m / report.cpu_count) * 100)

        # Memory (/proc/meminfo)
        meminfo = _run(conn, "cat /proc/meminfo")
        mem = {}
        for line in meminfo.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                nums = re.findall(r"\d+", v)
                if nums:
                    mem[k.strip()] = int(nums[0]) * 1024  # kB → bytes
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", mem.get("MemFree", 0))
        used = total - avail
        report.mem_total_gb = total / 1e9
        report.mem_used_gb = used / 1e9
        report.mem_free_gb = avail / 1e9
        report.mem_pct = (used / total * 100) if total else 0
        swap_total = mem.get("SwapTotal", 0)
        swap_free = mem.get("SwapFree", 0)
        report.swap_total_gb = swap_total / 1e9
        report.swap_used_gb = (swap_total - swap_free) / 1e9
        report.swap_pct = ((swap_total - swap_free) / swap_total * 100) if swap_total else 0

        # Disk (df -B1)
        df_raw = _run(conn, "df -B1 --output=target,size,used,avail,pcent -x tmpfs -x devtmpfs 2>/dev/null || df -B1 -x tmpfs -x devtmpfs")
        for line in df_raw.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 5:
                try:
                    mountpoint = parts[0]
                    total_b = int(parts[1])
                    used_b = int(parts[2])
                    free_b = int(parts[3])
                    pct_str = parts[4].replace("%", "")
                    pct = float(pct_str)
                    report.disks.append(DiskInfo(
                        mountpoint=mountpoint,
                        total_gb=total_b / 1e9,
                        used_gb=used_b / 1e9,
                        free_gb=free_b / 1e9,
                        use_pct=pct,
                    ))
                except (ValueError, IndexError):
                    continue

        # Top 5 CPU-consuming processes
        ps_raw = _run(conn, "ps aux --sort=-%cpu | head -6")
        for line in ps_raw.splitlines()[1:6]:
            cols = line.split(None, 10)
            if len(cols) >= 11:
                try:
                    report.top_processes.append(ProcessInfo(
                        pid=int(cols[1]),
                        user=cols[0],
                        cpu_pct=float(cols[2]),
                        mem_pct=float(cols[3]),
                        command=cols[10][:60],
                    ))
                except (ValueError, IndexError):
                    continue

        # Service status (systemctl)
        if check_services:
            for svc in check_services:
                status_raw = _run(conn, f"systemctl is-active {svc} 2>/dev/null || echo unknown")
                report.services[svc] = status_raw.strip()

        conn.close()

    except Exception as e:
        report.error = str(e)
        report.latency_ms = (time.time() - t0) * 1000

    return report
