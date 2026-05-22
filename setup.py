from setuptools import setup, find_packages

setup(
    name="devops-health",
    version="0.1.0",
    description="SSH-based server health dashboard — CPU, memory, disk, uptime in your terminal",
    author="bhupendra05",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.1",
        "rich>=13.0",
        "fabric>=3.0",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "devops-health=devops_health.cli:main",
        ]
    },
)
