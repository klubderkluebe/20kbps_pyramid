import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.txt')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

requires = [
    "urllib3==1.26.11",
    "python-dateutil==2.8.2",
    "plaster_pastedeploy",
    "pyramid==2.0",
    "pyramid_jinja2",
    "pyramid_debugtoolbar",
    "waitress==2.1.2",
    "psycopg2==2.9.5",
    "alembic==1.9.1",
    "pyramid_retry",
    "pyramid_tm",
    "SQLAlchemy==1.4.45",
    "transaction==3.0.1",
    "zope.sqlalchemy==1.6",
    "beautifulsoup4==4.11.1",
    "pyramid_ipython",
    "mutagen==1.46.0",
    "php-whisperer==2.2.0",
    "html5lib==1.1",
    "requests==2.28.1",
    "pathvalidate==2.5.2",
    "google==3.0.0",
    "protobuf==4.21.12",
    "googleapis-common-protos==1.57.1",
    "google-api-core==2.11.0",
    "google-cloud-core==2.3.2",
    "google-cloud-storage==2.7.0",
    "pyramid_nacl_session",
    "internetarchive==3.2.0",
    "shortuuid==1.0.11",
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
