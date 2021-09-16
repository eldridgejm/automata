from setuptools import setup, find_packages


setup(
    name="automata",
    version="0.0.0",
    packages=find_packages(),
    install_requires=["pyyaml", "cerberus", "jinja2"],
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "automata = automata:cli",
        ]
    },
)
