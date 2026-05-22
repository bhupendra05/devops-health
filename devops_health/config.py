"""Load host inventory from YAML or JSON config."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class Host:
    name: str
    hostname: str
    port: int = 22
    user: str = "root"
    key_file: Optional[str] = None
    password: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    @property
    def connect_kwargs(self) -> dict:
        kw: dict = {}
        key = self.key_file or os.environ.get("SSH_KEY_FILE")
        if key:
            kw["key_filename"] = os.path.expanduser(key)
        if self.password:
            kw["password"] = self.password
        return kw


def load_hosts(config_path: str) -> List[Host]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    hosts = []
    for entry in data.get("hosts", []):
        hosts.append(
            Host(
                name=entry["name"],
                hostname=entry["hostname"],
                port=entry.get("port", 22),
                user=entry.get("user", "root"),
                key_file=entry.get("key_file"),
                password=entry.get("password"),
                tags=entry.get("tags", []),
            )
        )
    return hosts


EXAMPLE_CONFIG = """\
hosts:
  - name: web-01
    hostname: 192.168.1.10
    user: ubuntu
    port: 22
    key_file: ~/.ssh/id_rsa
    tags: [web, production]

  - name: db-01
    hostname: 192.168.1.20
    user: ubuntu
    key_file: ~/.ssh/id_rsa
    tags: [database, production]

  - name: dev-server
    hostname: dev.example.com
    user: admin
    key_file: ~/.ssh/id_ed25519
    tags: [development]
"""
