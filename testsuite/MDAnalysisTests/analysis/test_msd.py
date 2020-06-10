# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 fileencoding=utf-8
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
# This module written by Hugo MacDermott-Opeskin 2020

from __future__ import division, absolute_import, print_function


import MDAnalysis as mda
from MDAnalysis.analysis.msd import EinsteinMSD as MSD

from numpy.testing import (assert_array_less,
                           assert_almost_equal, assert_equal)
import numpy as np

from MDAnalysisTests.datafiles import PSF, DCD, RANDOM_WALK, RANDOM_WALK_TOPO

import pytest
import tidynamics


@pytest.fixture(scope='module')
def SELECTION():
    selection = 'backbone and name CA and resid 1-10'
    return selection


@pytest.fixture(scope='module')
def NSTEP():
    nstep = 5000
    return nstep


@pytest.fixture(scope='module')
def u():
    return mda.Universe(PSF, DCD)


@pytest.fixture(scope='module')
def random_walk_u():
    # 100x100
    return mda.Universe(RANDOM_WALK_TOPO, RANDOM_WALK)


@pytest.fixture(scope='module')
def msd(u, SELECTION):
    # non fft msd
    m = MSD(u, SELECTION, msd_type='xyz', fft=False)
    m.run()
    return m


@pytest.fixture(scope='module')
def msd_fft(u, SELECTION):
    # fft msd
    m = MSD(u, SELECTION, msd_type='xyz', fft=True)
    m.run()
    return m


@pytest.fixture(scope='module')
def step_traj(NSTEP):  # constant velocity
    x = np.arange(NSTEP)
    traj = np.vstack([x, x, x]).T
    traj_reshape = traj.reshape([NSTEP, 1, 3])
    u = mda.Universe.empty(1)
    u.load_new(traj_reshape)
    return u


@pytest.fixture(scope='module')
def step_traj_arr(NSTEP):  # constant velocity
    x = np.arange(NSTEP)
    traj = np.vstack([x, x, x]).T
    return traj


def random_walk_3d(NSTEP):
    np.random.seed(1)
    steps = -1 + 2*np.random.randint(0, 2, size=(NSTEP, 3))
    traj = np.cumsum(steps, axis=0)
    traj_reshape = traj.reshape([NSTEP, 1, 3])
    u = mda.Universe.empty(1)
    u.load_new(traj_reshape)
    return u, traj


def characteristic_poly(n, d):  # polynomial that describes unit step traj MSD
    x = np.arange(0, n)
    y = d*x*x
    return y


def test_selection_works(msd):
    # test some basic size and shape things
    assert_equal(msd._n_particles, 10)


def test_fft_vs_simple_default(msd, msd_fft):
    # testing on the  PSF, DCD trajectory
    timeseries_simple = msd.timeseries
    timeseries_fft = msd_fft.timeseries
    assert_almost_equal(timeseries_simple, timeseries_fft, decimal=4)


def test_fft_vs_simple_default_per_particle(msd, msd_fft):
    # check fft and simple give same result per particle
    per_particle_simple = msd.msds_by_particle
    per_particle_fft = msd_fft.msds_by_particle
    assert_almost_equal(per_particle_simple, per_particle_fft, decimal=4)


@pytest.mark.parametrize("dim", ['xyz', 'xy', 'xz', 'yz', 'x', 'y', 'z'])
def test_fft_vs_simple_all_dims(u, SELECTION, dim):
    # check fft and simple give same result for each dimensionality
    m_simple = MSD(u, SELECTION, msd_type=dim, fft=False)
    m_simple.run()
    timeseries_simple = m_simple.timeseries
    m_fft = MSD(u, SELECTION, msd_type=dim, fft=True)
    m_fft.run()
    timeseries_fft = m_fft.timeseries
    assert_almost_equal(timeseries_simple, timeseries_fft, decimal=4)


@pytest.mark.parametrize("dim", ['xyz', 'xy', 'xz', 'yz', 'x', 'y', 'z'])
def test_fft_vs_simple_all_dims_per_particle(u, SELECTION, dim):
    # check fft and simple give same result for each particle in each dimension
    m_simple = MSD(u, SELECTION, msd_type=dim, fft=False)
    m_simple.run()
    per_particle_simple = m_simple.msds_by_particle
    m_fft = MSD(u, SELECTION, msd_type=dim, fft=True)
    m_fft.run()
    per_particle_fft = m_fft.msds_by_particle
    assert_almost_equal(per_particle_simple, per_particle_fft, decimal=4)


@pytest.mark.parametrize("dim, dim_factor", \
[('xyz', 3), ('xy', 2), ('xz', 2), ('yz', 2), ('x', 1), ('y', 1), ('z', 1)])
def test_simple_step_traj_all_dims(step_traj, NSTEP, dim, dim_factor):
    # testing the "simple" algorithm on constant velocity trajectory
    # should fit the polynomial y=dim_factor*x**2
    m_simple = MSD(step_traj, 'all', msd_type=dim, fft=False)
    m_simple.run()
    poly = characteristic_poly(NSTEP, dim_factor)
    assert_almost_equal(m_simple.timeseries, poly, decimal=4)

@pytest.mark.parametrize("dim, dim_factor", \
[('xyz', 3), ('xy', 2), ('xz', 2), ('yz', 2), ('x', 1), ('y', 1), ('z', 1)])
def test_simple_start_stop_step_all_dims(step_traj, NSTEP, dim, dim_factor):
    # testing the "simple" algorithm on constant velocity trajectory
    # test start stop step is working correctly
    m_simple = MSD(step_traj, 'all', msd_type=dim, fft=False)
    m_simple.run(start=10, stop=1000, step=10)
    poly = characteristic_poly(NSTEP, dim_factor)
    assert_almost_equal(m_simple.timeseries, poly[10:1000:10], decimal=4)


@pytest.mark.parametrize("dim, dim_factor", \
[('xyz', 3), ('xy', 2), ('xz', 2), ('yz', 2), ('x', 1), ('y', 1), ('z', 1)])
def test_fft_step_traj_all_dims(step_traj, NSTEP, dim, dim_factor):
    # testing the fft algorithm on constant velocity trajectory
    # this should fit the polynomial y=dim_factor*x**2
    # fft based tests require a slight decrease in expected prescision
    # primarily due to roundoff in fft(ifft()) calls.
    # relative accuracy expected to be around ~1e-12
    m_simple = MSD(step_traj, 'all', msd_type=dim, fft=True)
    m_simple.run()
    poly = characteristic_poly(NSTEP, dim_factor)
    # this was relaxed from decimal=4 for numpy=1.13 test
    assert_almost_equal(m_simple.timeseries, poly, decimal=3)

@pytest.mark.parametrize("dim, dim_factor", \
[('xyz', 3), ('xy', 2), ('xz', 2), ('yz', 2), ('x', 1), ('y', 1), ('z', 1)])
def test_fft_start_stop_step_all_dims(step_traj, NSTEP, dim, dim_factor):
    # testing the fft algorithm on constant velocity trajectory
    # test start stop step is working correctly
    m_simple = MSD(step_traj, 'all', msd_type=dim, fft=True)
    m_simple.run(start=10, stop=1000, step=10)
    poly = characteristic_poly(NSTEP, dim_factor)
    assert_almost_equal(m_simple.timeseries, poly[10:1000:10], decimal=3)


def test_random_walk_u_simple(random_walk_u):
    # regress against random_walk test data
    msd_rw = MSD(random_walk_u, 'all', msd_type='xyz', fft=False)
    msd_rw.run()
    norm = np.linalg.norm(msd_rw.timeseries)
    val = 3932.39927487146
    assert_almost_equal(norm, val, decimal=5)


def test_random_walk_u_fft(random_walk_u):
    # regress against random_walk test data
    msd_rw = MSD(random_walk_u, 'all', msd_type='xyz', fft=True)
    msd_rw.run()
    norm = np.linalg.norm(msd_rw.timeseries)
    val = 3932.39927487146
    assert_almost_equal(norm, val, decimal=5)
