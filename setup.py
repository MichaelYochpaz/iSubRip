from __future__ import annotations

import re
from pathlib import Path
from setuptools import find_packages, setup

CURRENT_PATH = Path(__file__).parent.absolute()
PACKAGE_NAME = "isubrip"
README_PATH = CURRENT_PATH / "README.md"


def get_version() -> str:
    init_file_path = CURRENT_PATH / PACKAGE_NAME / "__init__.py"
    version_regex = r"^__version__ = ['\"](\d+(?:\.\d+){2,3})['\"]"

    if not init_file_path.exists():
        raise FileNotFoundError(f"{init_file_path} file is missing.")

    with open(init_file_path, 'r') as fp:
        file_data = fp.read()

    for line in file_data.splitlines():
        if line.startswith("__version__"):
            if result := re.match(version_regex, line).group(1):
                return result

            else:
                raise RuntimeError('__version__ assignment does not match expected regex.')

    raise RuntimeError('Unable to find version string.')


def get_long_description() -> str:
    readme_path = CURRENT_PATH / "README.md"

    if not readme_path.exists():
        raise FileNotFoundError(f"{readme_path} file is missing.")

    with open(readme_path, "r") as file:
        return file.read()


setup(
    name=PACKAGE_NAME,
    version=get_version(),
    author="Michael Yochpaz",
    license="MIT",
    license_files=('LICENSE',),
    description="A Python package for scraping and downloading subtitles from iTunes movie pages.",
    long_description=get_long_description(),
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
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    keywords=["iTunes", "AppleTV", "movies", "subtitles", "scrape", "scraper", "download", "m3u8"],
    packages=find_packages(where=str(CURRENT_PATH)),
    package_data={PACKAGE_NAME: ["resources/*"]},
    python_requires=">=3.8",
    install_requires=["aiohttp", "m3u8", "mergedeep", "pydantic", "requests", "tomli"],
    entry_points={
        "console_scripts":
            [f"{PACKAGE_NAME} = {PACKAGE_NAME}.__main__:main"]
    },
)
