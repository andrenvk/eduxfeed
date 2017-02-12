from setuptools import setup


with open('README.rst') as f:
    long_description = f.read()


setup(
    name='eduxfeed',
    version='0.1.0',
    description='eduxfeed keeps you up to date with edux',
    long_description=long_description,
    author='Ondrej Novak',
    author_email='novako20@fit.cvut.cz',
    keywords='edux',
    license='MIT',
    url='https://github.com/andrenvk/eduxfeed',
    packages=['eduxfeed'],
    package_data={'eduxfeed': [
        # docs included in MANIFEST.in
        'test/*',
        'test/fixtures/*',
        'templates/*',
        'auth.cfg.sample',
    ]},
    install_requires=[
        'Flask',
        'click',
        'requests',
        'beautifulsoup4',
    ],
    tests_require=[
        'pytest',
        'flexmock',
    ],
    setup_requires=['pytest-runner'],
    entry_points={
        'console_scripts': [
            'eduxfeed = eduxfeed.run:run',
        ],
    },
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Flask',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
    ],
    zip_safe=False,
)
