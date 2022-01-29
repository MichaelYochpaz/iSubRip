from setuptools import setup

with open("README.md", "r") as file:
    long_description = file.read()

setup(
    name="isubrip",
    version="2.0.0",
    author="Michael Yochpaz",
    license="MIT",
    license_files = ('LICENSE',),
    description="A Python package for scraping and downloading subtitles from iTunes movie pages using only a URL (no account / purchase required).",
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
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10"
    ],

    keywords=["iTunes", "movies", "subtitles", "scrape", "scraper", "download", "m3u8"],
    packages=["isubrip"],
    install_requires=["beautifulsoup4", "lxml", "m3u8", "mergedeep", "requests", "tomli", "xdg"],
    package_data={"isubrip": ["resources/*"]},
    python_requires=">=3.6",
    entry_points={
        "console_scripts":
            ["isubrip = isubrip.__main__:main"]
    },
)
