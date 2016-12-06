from setuptools import setup

setup(
    name='nicotools',
    version='1.0.0',
    packages=['nicotools'],
    package_data={'nicotools': ['nicotools/stubs/*']},
    url='https://github.com/mo-san/niconico-tools',
    license='MIT License',
    author='Masaki Taniguchi',
    author_email='window100@gmail.com',
    description='Downloading videos, comments and thumbnails and handling your Mylists.',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: Japanese',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5'
    ],
    include_package_data=True,
    keywords=['niconico', 'ニコニコ動画'],
    install_requires=[
        'requests',
        'prettytable',
        'progressbar2'
    ],
    entry_points={
        'console_scripts': ['nicodown = nicotools.nicodown:main',
                            'nicoml = nicotools.nicoml:main']
    }
)
