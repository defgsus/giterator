import re
import sys

VERSION = None

# get the version without parsing the package
#   because requirements might not be installed
with open("giterator/_version.py") as fp:
    text = fp.read()
    for match in re.finditer(r"version = \((\d+), (\d+), (\d+)\)", text, re.MULTILINE):
        VERSION = "%s.%s.%s" % tuple(match.groups())


if not VERSION:
    raise ValueError("Can not read version from elastipy/_version.py")


if len(sys.argv) > 1 and sys.argv[1] == "--version":
    print(VERSION)

else:
    from setuptools import setup, find_namespace_packages

    def get_long_description():
        with open("./README.md") as fp:
            text = fp.read()
        try:
            with open("./CHANGELOG.md") as fp:
                text += "\n\n" + fp.read()
        except IOError:
            pass
        return text

    def get_packages():
        packages = ['giterator']
        packages += find_namespace_packages(include=['giterator.*'])
        return packages

    setup(
        name='giterator',
        version=VERSION,
        description='A python iterator through git commits.',
        long_description=get_long_description(),
        long_description_content_type="text/markdown",
        url='https://github.com/defgsus/giterator/',
        author='s.berke',
        author_email='s.berke@netzkolchose.de',
        license='MIT',
        packages=get_packages(),
        zip_safe=False,
        keywords="git repository data access",
        python_requires='>=3.6, <4',
        install_requires=[
            "python-dateutil>=2.8.2",
        ],
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Intended Audience :: Developers',
            'Intended Audience :: Information Technology',
            'Natural Language :: English',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
            'Programming Language :: Python :: 3.10',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Topic :: Scientific/Engineering :: Information Analysis',
            'Typing :: Typed',
        ],
    )
