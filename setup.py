from setuptools import setup

setup(
    name='notion_export_enhancer',
    version='0.0.7',
    description='Export and _enhance_, takes Notion\'s export and makes it just a bit more usable.',
    long_description=open('README.md', 'r').read(),
    long_description_content_type="text/markdown",
    url='https://github.com/Cobertos/notion_export_enhancer/',
    author='Cobertos',
    author_email='me+python@cobertos.com',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Office/Business :: News/Diary',
        'Topic :: System :: Filesystems',
        'Topic :: Text Processing :: Markup :: Markdown',
        'Topic :: Utilities'
    ],
    install_requires=[
        'backoff>=1.11.0',
        'emoji_extractor>=1.0.19',
        'notion-cobertos-fork>=0.0.29',
    ],
    keywords='notion notion.so notion-py markdown md export enhance enhancer',
    packages=['notion_export_enhancer']
)
