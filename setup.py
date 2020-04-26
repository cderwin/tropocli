from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='tropocli',
    version='0.0.1',
    install_requires=requirements,
    author='Cameron Derwin',
    author_email='camderwin@gmail.com',
    description="A CLI to directly validate and deploy cloudformation template written in troposphere',
    url='https://github.com/cderwin/tropocli',
    license='MIT License',
    packages=find_packages(exclude=('tests', 'docs')),
    test_suite="tests",
    scripts=['bin/gimme-aws-creds', 'bin/gimme-aws-creds.cmd'],
    classifiers=[
        'Natural Language :: English',
        'Programming Language :: Python :: 3 :: Only',
        'License :: OSI Approved :: MIT License',
    ]
)
