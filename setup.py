from setuptools import setup

with open('README.rst') as f:
    readme = f.read()

setup(
    name='nicotools',
    version='1.0.2',
    packages=['nicotools'],
    # package_data={'nicotools': ['nicotools/stubs/*']},
    # include_package_data=True,
    url='https://github.com/mo-san/niconico-tools',
    license='MIT License',
    author='Masaki Taniguchi',
    author_email='window100@gmail.com',
    description=('Downloading videos, comments and thumbnails and'
                 ' handling your Mylists on niconico (ニコニコ動画).'),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: Japanese',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ],
    long_description=readme,
    keywords=['niconico', 'nicovideo', 'ニコニコ動画'],
    install_requires=[
        'requests',
        'prettytable',
        'bs4',
        'aiohttp',
        'tqdm'
    ],
    entry_points={
        'console_scripts': ['nicotools = nicotools.__init__:main']
    }
)
