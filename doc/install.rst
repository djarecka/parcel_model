.. _install:

Installation
============

To grab and build the latest version of the model, you should use ``pip`` and
point it to the source code `repository`_ on github:

.. code-block:: bash

    $ pip install git+git://github.com/darothen/parcel_model.git

This should automatically build the necessary Cython modules and export the
code package to your normal package installation directory. If you wish to
simply build the code and run it in place, clone the `repository`_, navigate
to it in a terminal, and invoke the build command by hand:


.. code-block:: bash

    $ python setup.py build_ext --inplace

This should produce the compiled file `parcel_aux.so` in the model package.
You can also install the code from the cloned source directory by invoking
``pip install`` from within it; this is useful if you're updating or
modifying the model, since you can install an "editable" package which
points directly to the git-monitored code:


.. code-block:: bash

    $ cd path/to/parcel_model/
    $ pip install -e .


Dependencies
------------

This code was originally written for Python 2.7, and then
`futurized <http://python-future.org/>`_ to Python 3.3+ with hooks for
backwards compatibility. By far, the simplest way to run this code is to grab a
scientific python distribution, such as
`Anaconda <https://store.continuum.io/cshop/anaconda/>`_. This code should work
out-of-the box with almost all dependencies filled (exception being numerical
solvers) on a recent version (1.2+) of this distribution. To faciliate this,
`conda <http://conda.pydata.org/docs/>`_ environments for Python versions 2.7
and 3.4+ are provided in the ``parcel_model/ci`` directory.

Necessary dependencies
^^^^^^^^^^^^^^^^^^^^^^

- `numpy <http://www.numpy.org/>`_

- `scipy <http://www.scipy.org/>`_

- `pandas <http://pandas.pydata.org/>`_

- `Cython <http://cython.org/>`_

- `future <http://python-future.org/>`_

- `Assimulo <http://www.jmodelica.org/assimulo_home/index.html>`_

.. note::

    As of version 1.2.0, the model integration components are being re-written
    and only the CVODE interface is exposed. As such, Assimulo is temporarily
    a core and required dependency; in the future the other solvers will
    be re-enabled. For best results, you will want to `manually install
    Assimulo <http://www.jmodelica.org/assimulo_home/installation.html>`_, as
    I've encountered issues using the available `pip` or `conda` packages.

Numerical solver dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **LSODA** - `scipy <http://www.scipy.org/>`_ or
  `odespy <https://github.com/hplgit/odespy/>`_

- **VODE**, **LSODE** - `odespy <https://github.com/hplgit/odespy/>`_

- **CVODE** - `Assimulo <http://www.jmodelica.org/assimulo_home/index.html>`_

Recommended additional packages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- `matplotlib <http://matplotlib.sourceforge.net/>`_

- `seaborn <http://stanford.edu/~mwaskom/software/seaborn/index.html>`_

- `PyYAML <http://pyyaml.org/wiki/PyYAMLDocumentation>`_

- `xarray <http://xarray.pydata.org/en/stable/>`_

Testing
-------

A nose test-suite is under construction. To check that your model is configured
and running correctly, you copy and run the notebook corresponding to the
:ref:`basic run example <example_basic>`, or run the command-line interface
version of the model with the pre-packed simple run case:

.. code-block:: bash

    $ cd path/to/parcel_model/
    $ ./run_parcel examples/simple.yml


Bugs / Suggestions
------------------

The code has an
`issue tracker on github <https://github.com/darothen/parcel_model/issues>`_
and I strongly encourage you to note any problems with the model there, such
as typos or weird behavior and results. Furthermore, I'm looking for ways to
expand and extend the model, so if there is something you might wish to see
added, please note it there or `send me an e-mail <mailto:darothen@mit.edu>`_.
The code was written in such a way that it should be trivial to add physics in a modular fashion.

.. _repository: http://github.com/darothen/parcel_model
