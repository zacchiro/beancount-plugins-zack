from setuptools import find_packages, setup

setup(
    name="beancount-plugins-zack",
    version="0.0.1.dev0",
    description="Zack's plugins for Beancount",
    author="Stefano Zacchiroli",
    author_email="zack@upsilon.cc",
    url="https://github.com/zacchiro/beancount-plugins-zack",
    packages=find_packages("src"),
    package_dir={"": "src"},
    zip_safe=False,
    install_requires=["beancount"],
    extras_require={
        "cerberus": ["cerberus", "pyyaml"],
    },
)
