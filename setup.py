from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).parent
README = ROOT / "README.md"

long_description = README.read_text(encoding="utf-8") if README.exists() else ""

setup(
    name="astrobridge",
    version="0.1.0",
    description="Astronomical source matching and cross-catalog orchestration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires=">=3.9",
    packages=find_packages(),
    py_modules=["demo"],
    install_requires=[
        "pydantic",
        "pydantic-settings",
        "numpy",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0",
            "pytest-asyncio>=0.23",
        ],
        "live": [
            "pyvo>=1.5",
        ],
        "web": [
            "fastapi>=0.111",
            "uvicorn>=0.30",
            "httpx>=0.27",
        ],
    },
    entry_points={
        "console_scripts": [
            "astrobridge-demo=demo:main",
            "astrobridge-web=astrobridge.web.app:main",
        ]
    },
    include_package_data=True,
)
