from setuptools import setup, find_packages

setup(
    name="astrobridge",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic",
        "pydantic-settings",
        "numpy",
    ],
)
