============
Optimization
============

.. currentmodule:: nabs.optimize

Concept
=======
A core part of the ``nabs`` library is support for the optimization of various
process variables using the `bluesky <https://blueskyproject.io/bluesky>`_
scanning framework. The physics behind
every use case may be wildly different, but the main idea is to have a set of
plans that scan a "motor" until a specific criteria is observed on a separate
"detector". ``nabs`` contains three complete plans for different situations;
`maximize`, `minimize`, and `walk_to_target`.  Hopefully
the intention behind each is self-evident based on the name.

There are numerous algorithms to locate extrema within a univariate function,
each with their own strengths and weaknesses. To deal with this ``nabs`` takes
inspiration from the `scipy
<https://docs.scipy.org/doc/scipy-1.0.0/reference/generated/scipy.optimize.minimize.html>`_
library allowing the user to select their chosen methodology as the function
(or in our case create the plan). A brief description of available methods are
described below.


Available Methods
=================

Golden Section Search
^^^^^^^^^^^^^^^^^^^^^
``method="golden"``

`Golden Section Search <https://en.wikipedia.org/wiki/Golden-section_search>`_
approaches finding extrema by reducing a range known to contain the extrema
step by step. Every iteration selects a "probe" point within our known range
and uses the result to reduce the search-space in one direction or the other.
By cleverly choosing these search points based on the "golden ratio", the
region is reduced by the same factor regardless of the luck involved with
choosing probe points.

============= =================================================================
Strengths     The algorithm has the benefit of converging in a known number of
              steps based on the size of the given search-space and the desired
              resolution. Also, because the methodolgy involves no fitting or
              gradient calculations it may be more robust against noise.

Weaknesses    The method assumes that the underlying functionality is unimodal.
              If there are any local extrema this method may not converge to
              the expected point. Finally, the motor is required to move
              bi-directionally, so if there are issues with backlash this
              method should not be used.
============= =================================================================
