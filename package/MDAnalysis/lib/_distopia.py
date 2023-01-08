# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
#
# MDAnalysis --- https://www.mdanalysis.org
# Copyright (c) 2006-2017 The MDAnalysis Development Team and contributors
# (see the file AUTHORS for the full list of names)
#
# Released under the GNU Public Licence, v2 or any higher version
#
# Please cite your use of MDAnalysis in published work:
#
# R. J. Gowers, M. Linke, J. Barnoud, T. J. E. Reddy, M. N. Melo, S. L. Seyler,
# D. L. Dotson, J. Domanski, S. Buchoux, I. M. Kenney, and O. Beckstein.
# MDAnalysis: A Python package for the rapid analysis of molecular dynamics
# simulations. In S. Benthall and S. Rostrup editors, Proceedings of the 15th
# Python in Science Conference, pages 102-109, Austin, TX, 2016. SciPy.
# doi: 10.25080/majora-629e541a-00e
#
# N. Michaud-Agrawal, E. J. Denning, T. B. Woolf, and O. Beckstein.
# MDAnalysis: A Toolkit for the Analysis of Molecular Dynamics Simulations.
# J. Comput. Chem. 32 (2011), 2319--2327, doi:10.1002/jcc.21787
#

"""Stub module for distopia --- :mod:`MDAnalysis.analysis.distopia`
===================================================================

This module is a stub to provide distopia distance functions to `distances.py`
as a selectable backend.
"""

# check for distopia
try:
    import distopia
except ImportError:
    HAS_DISTOPIA = False
else:
    HAS_DISTOPIA = True

from .c_distances import calc_bond_distance_triclinic as _calc_bond_distance_triclinic_serial
import warnings

def calc_bond_distance_ortho(numpy.ndarray coords1, numpy.ndarray coords2,
                             numpy.ndarray box, numpy.ndarray results) -> None:

    results = distopia.calc_bonds_ortho_float(coords1, coords2, box[:3], results=results.astype(np.float32))
    # upcast is currently required, change for 3.0, see #3927
    results = results.astype(np.float64)

def calc_bond_distance(numpy.ndarray coords1, numpy.ndarray coords2, numpy.ndarray results) -> None:
    results = distopia.calc_bonds_no_box_float(coords1, coords2, results=results.astype(np.float32))
    # upcast is currently required, change for 3.0, see #3927
    results = results.astype(np.float64)

def calc_bond_distance_triclinic(numpy.ndarray coords1, numpy.ndarray coords2,
                             numpy.ndarray box, numpy.ndarray results) -> None:
    # redirect to serial backend
    warnings.warn("distopia does not support triclinic boxes, using serial backend instead.")
    _calc_bond_distance_triclinic_serial(coords1, coords2, box, results)
