from os import PathLike
from pathlib import Path
from typing import Union

from setuptools import setup


def get_version(relative_path: Union[str, PathLike]) -> str:
    current_path = Path(__file__).parent.absolute()

    with open(current_path / relative_path, 'r') as fp:
        file_data: str = fp.read()

    for line in file_data.splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]

    raise RuntimeError("Unable to find version string.")


PACKAGE_NAME: str = "isubrip"

with open("README.md", "r") as file:
    long_description = file.read()


setup(
    name=PACKAGE_NAME,
    version=get_version(Path(PACKAGE_NAME) / "__init__.py"),
    author="Michael Yochpaz",
    license="MIT",
    license_files=('LICENSE',),
    description="A Python package for scraping and downloading subtitles from iTunes movie pages.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MichaelYochpaz/iSubRip",

    project_urls={
        "Bug Reports": "https://github.com/MichaelYochpaz/iSubRip/issues",
        "Source": "https://github.com/MichaelYochpaz/iSubRip"
    },

    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Developers",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10"
    ],

    keywords=["iTunes", "movies", "subtitles", "scrape", "scraper", "download", "m3u8"],
    packages=["isubrip"],
    install_requires=["aiohttp", "beautifulsoup4", "lxml", "m3u8", "mergedeep", "requests", "tomli"],
    package_data={"isubrip": ["resources/*"]},
    python_requires=">=3.8",
    entry_points={
        "console_scripts":
            ["isubrip = isubrip.__main__:main"]
    },
)
