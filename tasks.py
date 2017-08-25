# -*- coding: utf-8 -*-
from sys import platform
from os import environ
from invoke import Collection, task
from pathlib import Path


PROJECT_DIR = Path(__file__).parent


def walk_files(directory: Path):
    for _insider in directory.iterdir():
        if _insider.is_dir():
            subs = walk_files(_insider.resolve())
            for _sub in subs:
                yield _sub.resolve()
        else:
            yield _insider.resolve()


def find_all(glob):
    for f in walk_files(PROJECT_DIR):
        if glob in f.name:
            yield f


@task
def pep8(ctx, folder="csv2df"):
    path = PROJECT_DIR / "src" / folder
    files = filter(lambda x: x.suffix == ".py", walk_files(path))
    for f in files:
        print("Formatting", f)
        # FIXME: may use 'import autopep8' without console
        ctx.run("autopep8 --aggressive --aggressive --in-place {}".format(f))


@task
def clean(ctx):
    """Delete all compiled Python files"""
    for f in find_all(".pyc"):
        print("Removing", f)
        f.unlink()


@task
def lint(ctx, folder="src/csv2df"):
    """Check style with flake8

       See more flake8 usage at:
           https://habrahabr.ru/company/dataart/blog/318776/
    """
    # E501 line too long
    # --max-line-length=100
    ctx.run('flake8 {} --exclude test* --ignore E501'.format(folder))


@task
def rst(ctx):
    # build new rst files with sphinx
    # FIXME: must check / appearance issues:

    # 1. documentation page shows intro.rst and glossary.rst for the project
    #     and links to src/ packages/folders:
    #          download
    #          word2csv (will rename, it is now called word)
    #          csv2df
    #          access_data
    #          frontage
    #    The link is a module name, possibly followed by a short comment.

    #    Question: can this comment be ofr example __init__ docstring? Or just
    #    enter harcoded test or omit, showing this is not a priority.

    # 2. in csv2df page I want a listing of modules with their docstrings, no
    #    docs for module contents. In listing I would prefer to control order of
    #    modules listed, eg. make 'helpers' first and 'emitter', 'validator' last.

    # 3. when clicking on module name I get its documentation

    ctx.run("sphinx-apidoc -efM -o doc src\csv2df *test_*")


@task
def doc(ctx):
    ctx.run("doc\make.bat html")
    ctx.run("start doc\_build\html\index.html")
    # TODO: 
    # upload all files from doc\_build\html\ 
    # to aws https://mini-kep-docs.s3.amazonaws.com/
    # mini-csv2df-docs + is region neded?


@task
def github(ctx):
    ctx.run("start https://github.com/epogrebnyak/mini-csv2df")


@task
def test(ctx):
    ctx.run("py.test") #--cov=csv2df

# TODO:
# coverage annotate -d csv2df\tests\annotate -i csv2df/runner.py

@task
def cov(ctx):
    ctx.run("py.test --cov=csv2df")
    ctx.run("coverage report --omit=*tests*,*__init__*")


@task
def ls(ctx):
    """List directory"""
    cmd = "dir /b"
    result = ctx.run(cmd, hide=False, warn=True)
    print(result.ok)
    print(result.stdout.splitlines())


ns = Collection()
for t in [clean, pep8, ls, cov, test, doc, rst, github, lint]:
    ns.add_task(t)


# Workaround for Windows execution
if platform == 'win32':
    # This is path to cmd.exe
    ns.configure({'run': {'shell': environ['COMSPEC']}})




##########################################################################
# GLOBALS                                                                       #
##########################################################################

# PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
#BUCKET = {{ cookiecutter.s3_bucket }}
#PROFILE = {{ cookiecutter.aws_profile }}
#PROJECT_NAME = {{ cookiecutter.repo_name }}
#PYTHON_INTERPRETER = {{ cookiecutter.python_interpreter }}

##########################################################################
# COMMANDS                                                                      #
##########################################################################

# Make Dataset
#data: requirements
#	$(PYTHON_INTERPRETER) src/data/make_dataset.py


# Upload Data to S3
# sync_data_to_s3:
# ifeq (default,$(PROFILE))
#	aws s3 sync data/ s3://$(BUCKET)/data/
# else
#	aws s3 sync data/ s3://$(BUCKET)/data/ --profile $(PROFILE)
# endif

# Download Data from S3
# sync_data_from_s3:
# ifeq (default,$(PROFILE))
#	aws s3 sync s3://$(BUCKET)/data/ data/
# else
#	aws s3 sync s3://$(BUCKET)/data/ data/ --profile $(PROFILE)
# endif
