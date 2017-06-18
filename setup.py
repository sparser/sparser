from distutils.core import setup

setup(
    name='sparser',
    packages=['sparser'],
    version='0.2',
    description='String parsing and regular expressions for humans',
    long_description=open('README.md').read(),
    author='Scott Rogowski',
    author_email='scottmrogowski@gmail.com',
    license='MIT/X',
    url='https://github.com/sparser/sparser',
    keywords=['string parsing', 'string parser' 'regular expressions', 'regex', 'reverse templating'],
    classifiers=(
      'Programming Language :: Python :: 2',
      'Programming Language :: Python :: 3'
      )
    )
