===========================
Instructions for developers
===========================

Running unit tests
------------------

This version of simstock comes with a unit test suite, located within the ``tests/`` subdirectory. To run these tests, ensure you are in the base of the Simstock directory and run the following command: 

.. code-block:: bash

    poetry run python -m unittest -b -v

If you are using Conda instead of Poetry, then omit the ``poetry run`` command. For more information on modifying and adding tests, consult the ``unittest`` `documentation <https://docs.python.org/3/library/unittest.html>`_.

Generating and modifying the docs
---------------------------------

HTML docs are automatically generated from the docstrings within the Simstock source code. You can also include additional pages (such as this one) giving tutorials etc. 

To compile the docs into html, navigate into the ``docs`` subdirectory and run 

.. code-block:: bash

    poetry run make clean
    poetry run make html

If not using Poetry, then omit the ``poetry run`` directives.

All pages and docstrings within the documentation must be written in ``.rst`` format. This is similar to markdown. Refer to the `rst cheatsheet <https://bashtage.github.io/sphinx-material/rst-cheatsheet/rst-cheatsheet.html>`_ for a quick guide. All documentation .rst files are contained within ``docs/source/``. To add a new page to the documentation, create a new .rst file within ``docs/source/`` and then add the file name (minus the .rst extension)  into toctree list within ``docs/source/index.rst``.

Once compiled, the html documents can be found within ``docs/build/html``.

.. note:: \ \ 

    After public release, the unittests will be run and the docs regenerated upon each push to Github using  `Github Actions <https://github.com/features/actions>`_.


Updating the yaml file from poetry
----------------------------------

Simstock has been largely developed using the poetry environment manager. However, support is also offered to conda users by compiling the poetry .toml file into a yaml file. This can be done automaically using the package `poetry2conda <https://github.com/dojeda/poetry2conda>`_. 

If you add a new dependency via poetry and want this to be reflected in the yaml file, run the command 

.. code-block:: bash

    poetry run poetry2conda pyproject.toml environment.yaml
