import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.txt')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

requires = [
    "urllib3==1.26.14",
    "python-dateutil",
    'plaster_pastedeploy',
    'pyramid',
    'pyramid_jinja2',
    'pyramid_debugtoolbar',
    'waitress',
    "psycopg2",
    'alembic',
    'pyramid_retry',
    'pyramid_tm',
    'SQLAlchemy==1.4.46',
    'transaction',
    'zope.sqlalchemy',
    "beautifulsoup4",
    "pyramid_ipython",
    "mutagen",
    "php-whisperer",
    "html5lib",
    "requests",
    "pathvalidate",
    "google-cloud-core==2.3.1",
    "google-cloud-storage",
    "pyramid_nacl_session",
    "internetarchive",
    "shortuuid",
]

tests_require = [
    'WebTest',
    'pytest',
    'pytest-cov',
]

setup(
    name='pyramidprj',
    version='0.0',
    description='pyramidprj',
    long_description=README + '\n\n' + CHANGES,
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Pyramid',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
    ],
    author='',
    author_email='',
    url='',
    keywords='web pyramid pylons',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    extras_require={
        'testing': tests_require,
    },
    install_requires=requires,
    entry_points={
        'paste.app_factory': [
            'main = pyramidprj:main',
        ],
        'console_scripts': [
            'initialize_pyramidprj_db=pyramidprj.scripts.initialize_db:main',
        ],
    },
)
