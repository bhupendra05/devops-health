"""Rich terminal rendering for health reports."""
from __future__ import annotations

from typing import List

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text
from rich import box

from devops_health.collector import HealthReport

console = Console()


def _pct_color(pct: float) -> str:
    if pct >= 90:
        return "bold red"
    if pct >= 75:
        return "yellow"
    return "green"


def _bar(pct: float, width: int = 20) -> str:
    filled = int(pct / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    color = _pct_color(pct)
    return f"[{color}]{bar}[/] {pct:.1f}%"


def render_summary_table(reports: List[HealthReport]) -> None:
    table = Table(
        title="Server Health Dashboard",
        box=box.ROUNDED,
        show_lines=True,
        expand=True,
    )
    table.add_column("Host", style="bold")
    table.add_column("Status")
    table.add_column("Uptime")
    table.add_column("CPU (1m)", justify="right")
    table.add_column("Memory")
    table.add_column("Disk (/)")
    table.add_column("Latency", justify="right")

    for r in reports:
        if not r.reachable:
            table.add_row(
                r.host,
                "[red]✗ UNREACHABLE[/]",
                "—", "—", "—", "—",
                f"{r.latency_ms:.0f}ms",
            )
            continue

        status = "[green]✓ OK[/]"

        # Find root disk
        root_disk = next((d for d in r.disks if d.mountpoint == "/"), None)
        disk_str = _bar(root_disk.use_pct) if root_disk else "—"

        table.add_row(
            r.host,
            status,
            r.uptime_human or "—",
            f"[{_pct_color(r.cpu_pct)}]{r.cpu_1m:.2f}[/] ({r.cpu_pct:.0f}%)",
            _bar(r.mem_pct),
            disk_str,
            f"{r.latency_ms:.0f}ms",
        )

    console.print(table)


def render_host_detail(r: HealthReport) -> None:
    if not r.reachable:
        console.print(
            Panel(
                f"[red]{r.error or 'Connection failed'}[/]",
                title=f"[bold red]{r.host}[/] — UNREACHABLE",
                border_style="red",
            )
        )
        return

    # Header
    console.print(
        Panel(
            f"[bold]{r.hostname or r.host}[/]  ·  {r.os_info}  ·  kernel {r.kernel}\n"
            f"[dim]Uptime:[/] {r.uptime_human}  "
            f"[dim]CPUs:[/] {r.cpu_count}  "
            f"[dim]Latency:[/] {r.latency_ms:.0f}ms",
            title=f"[bold cyan]{r.host}[/]",
            border_style="cyan",
        )
    )

    # CPU + Memory side by side
    cpu_text = (
        f"Load avg:  {r.cpu_1m:.2f}  {r.cpu_5m:.2f}  {r.cpu_15m:.2f}\n"
        f"Usage:     {_bar(r.cpu_pct)}"
    )
    mem_text = (
        f"Total:   {r.mem_total_gb:.1f} GB\n"
        f"Used:    {r.mem_used_gb:.1f} GB\n"
        f"Free:    {r.mem_free_gb:.1f} GB\n"
        f"Usage:   {_bar(r.mem_pct)}"
    )
    swap_text = (
        f"Total:   {r.swap_total_gb:.1f} GB\n"
        f"Used:    {r.swap_used_gb:.1f} GB  {_bar(r.swap_pct)}"
    ) if r.swap_total_gb else "No swap configured."

    console.print(
        Columns(
            [
                Panel(cpu_text, title="CPU", border_style="blue"),
                Panel(mem_text, title="Memory", border_style="green"),
                Panel(swap_text, title="Swap", border_style="dim"),
            ],
            equal=True,
        )
    )

    # Disk
    if r.disks:
        disk_table = Table(title="Disk Usage", box=box.SIMPLE, show_lines=True)
        disk_table.add_column("Mount")
        disk_table.add_column("Total", justify="right")
        disk_table.add_column("Used", justify="right")
        disk_table.add_column("Free", justify="right")
        disk_table.add_column("Usage")
        for d in sorted(r.disks, key=lambda x: -x.use_pct):
            disk_table.add_row(
                d.mountpoint,
                f"{d.total_gb:.1f}G",
                f"{d.used_gb:.1f}G",
                f"{d.free_gb:.1f}G",
                _bar(d.use_pct),
            )
        console.print(disk_table)

    # Top processes
    if r.top_processes:
        proc_table = Table(title="Top Processes (CPU)", box=box.SIMPLE)
        proc_table.add_column("PID", justify="right", style="dim")
        proc_table.add_column("User")
        proc_table.add_column("CPU%", justify="right")
        proc_table.add_column("MEM%", justify="right")
        proc_table.add_column("Command")
        for p in r.top_processes:
            color = _pct_color(p.cpu_pct)
            proc_table.add_row(
                str(p.pid),
                p.user,
                f"[{color}]{p.cpu_pct:.1f}[/]",
                f"{p.mem_pct:.1f}",
                p.command,
            )
        console.print(proc_table)

    # Services
    if r.services:
        svc_table = Table(title="Services", box=box.SIMPLE)
        svc_table.add_column("Service")
        svc_table.add_column("Status")
        for name, status in r.services.items():
            color = "green" if status == "active" else "red"
            svc_table.add_row(name, f"[{color}]{status}[/]")
        console.print(svc_table)
