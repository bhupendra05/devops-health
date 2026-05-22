"""CLI entry point for devops-health."""
from __future__ import annotations

import concurrent.futures
import json
import sys
from pathlib import Path

import click
from rich.console import Console

from devops_health.collector import HealthReport, collect
from devops_health.config import EXAMPLE_CONFIG, Host, load_hosts
from devops_health.display import console, render_host_detail, render_summary_table


@click.group()
def cli():
    """devops-health — SSH-based server health dashboard."""


@cli.command("check")
@click.option("--config", "-c", default="hosts.yml", show_default=True, help="Hosts config file")
@click.option("--host", "-H", default=None, help="Check only this host (by name)")
@click.option("--services", "-s", default="", help="Comma-separated services to check (e.g. nginx,postgres)")
@click.option("--detail/--summary", default=False, help="Show per-host detail or summary table")
@click.option("--workers", default=10, show_default=True, help="Parallel SSH workers")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def check_cmd(config, host, services, detail, workers, as_json):
    """Check health of all servers in the config."""
    try:
        hosts = load_hosts(config)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        console.print(f"[dim]Run: devops-health init  to create a sample config[/]")
        sys.exit(1)

    if host:
        hosts = [h for h in hosts if h.name == host]
        if not hosts:
            console.print(f"[red]Host '{host}' not found in {config}[/]")
            sys.exit(1)

    svc_list = [s.strip() for s in services.split(",") if s.strip()] if services else None

    reports: list[HealthReport] = []

    def _check(h: Host) -> HealthReport:
        return collect(h, check_services=svc_list)

    with console.status(f"Checking {len(hosts)} host(s)…", spinner="dots"):
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(hosts))) as pool:
            futures = {pool.submit(_check, h): h for h in hosts}
            for f in concurrent.futures.as_completed(futures):
                reports.append(f.result())

    # Sort by original order
    order = {h.name: i for i, h in enumerate(hosts)}
    reports.sort(key=lambda r: order.get(r.host, 99))

    if as_json:
        out = []
        for r in reports:
            out.append({
                "host": r.host,
                "reachable": r.reachable,
                "error": r.error,
                "uptime_human": r.uptime_human,
                "cpu_pct": r.cpu_pct,
                "cpu_load": [r.cpu_1m, r.cpu_5m, r.cpu_15m],
                "mem_pct": r.mem_pct,
                "mem_total_gb": r.mem_total_gb,
                "mem_used_gb": r.mem_used_gb,
                "disks": [
                    {"mount": d.mountpoint, "use_pct": d.use_pct, "free_gb": d.free_gb}
                    for d in r.disks
                ],
                "services": r.services,
                "latency_ms": r.latency_ms,
            })
        click.echo(json.dumps(out, indent=2))
        return

    if detail or len(hosts) == 1:
        for r in reports:
            render_host_detail(r)
            console.print()
    else:
        render_summary_table(reports)

    # Exit code 1 if any host unreachable or disk > 90%
    issues = [r for r in reports if not r.reachable]
    disk_issues = [
        r for r in reports
        if r.reachable and any(d.use_pct >= 90 for d in r.disks)
    ]
    if disk_issues:
        console.print(f"[yellow]⚠ Disk usage ≥90% on: {', '.join(r.host for r in disk_issues)}[/]")
    if issues:
        sys.exit(1)


@cli.command("watch")
@click.option("--config", "-c", default="hosts.yml", show_default=True)
@click.option("--interval", "-i", default=30, show_default=True)
@click.option("--services", "-s", default="")
@click.option("--workers", default=10)
def watch_cmd(config, interval, services, workers):
    """Continuously refresh the health dashboard."""
    import time
    from rich.live import Live

    try:
        hosts = load_hosts(config)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)

    svc_list = [s.strip() for s in services.split(",") if s.strip()] if services else None

    console.print(f"[bold]Live dashboard[/] — refreshing every {interval}s  [dim](Ctrl+C to stop)[/]\n")

    try:
        while True:
            reports = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(hosts))) as pool:
                futures = {pool.submit(collect, h, svc_list): h for h in hosts}
                for f in concurrent.futures.as_completed(futures):
                    reports.append(f.result())
            reports.sort(key=lambda r: r.host)

            console.clear()
            render_summary_table(reports)
            console.print(f"\n[dim]Next refresh in {interval}s…[/]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/]")


@cli.command("init")
@click.option("--output", "-o", default="hosts.yml", show_default=True)
def init_cmd(output):
    """Create a sample hosts.yml config file."""
    path = Path(output)
    if path.exists():
        console.print(f"[yellow]{output} already exists — not overwriting.[/]")
        return
    path.write_text(EXAMPLE_CONFIG)
    console.print(f"[green]Created[/] {output}")
    console.print(f"[dim]Edit it with your server details, then run: devops-health check[/]")


@cli.command("quickcheck")
@click.argument("hostname")
@click.option("--user", "-u", default="root", show_default=True)
@click.option("--port", "-p", default=22, show_default=True)
@click.option("--key", "-k", default=None, help="SSH private key path")
@click.option("--services", "-s", default="")
def quickcheck_cmd(hostname, user, port, key, services):
    """Quick one-off check of a single server (no config file needed)."""
    host = Host(
        name=hostname,
        hostname=hostname,
        port=port,
        user=user,
        key_file=key,
    )
    svc_list = [s.strip() for s in services.split(",") if s.strip()] if services else None

    with console.status(f"Connecting to {hostname}…"):
        report = collect(host, check_services=svc_list)

    render_host_detail(report)


def main():
    cli()


if __name__ == "__main__":
    main()
