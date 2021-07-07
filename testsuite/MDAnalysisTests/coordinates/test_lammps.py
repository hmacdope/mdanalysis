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
import bz2
import gzip
import os
import numpy as np
import pytest

import MDAnalysis as mda
from MDAnalysis import NoDataError

from numpy.testing import (assert_equal, assert_almost_equal)

from MDAnalysisTests import make_Universe
from MDAnalysisTests.coordinates.reference import (
    RefLAMMPSData, RefLAMMPSDataMini, RefLAMMPSDataDCD,
)
from MDAnalysisTests.datafiles import (
    LAMMPScnt, LAMMPShyd, LAMMPSdata, LAMMPSdata_mini, LAMMPSDUMP,
    LAMMPSDUMP_allcoords
)


def test_datareader_ValueError():
    from MDAnalysis.coordinates.LAMMPS import DATAReader
    with pytest.raises(ValueError):
        DATAReader('filename')


class _TestLammpsData_Coords(object):
    """Tests using a .data file for loading single frame.

    All topology loading from MDAnalysisTests.data is done in test_topology
    """

    @pytest.fixture(scope='class')
    def u(self):
        return mda.Universe(self.filename)

    def test_n_atoms(self, u):
        assert_equal(u.atoms.n_atoms, self.n_atoms)

    def test_coords(self, u):
        assert_equal(u.atoms[0].position, self.pos_atom1)

    def test_velos(self, u):
        assert_almost_equal(u.atoms[0].velocity, self.vel_atom1)

    def test_dimensions(self, u):
        assert_equal(u.dimensions, self.dimensions)

    def test_singleframe(self, u):
        with pytest.raises(StopIteration):
            u.trajectory.next()

    def test_seek(self, u):
        with pytest.raises(IndexError):
            u.trajectory[1]

    def test_seek_2(self, u):
        ts = u.trajectory[0]
        assert_equal(type(ts), mda.coordinates.base.Timestep)

    def test_iter(self, u):
        # Check that iterating works, but only gives a single frame
        assert len(list(iter(u.trajectory))) == 1


class TestLammpsData_Coords(_TestLammpsData_Coords, RefLAMMPSData):
    pass


class TestLammpsDataMini_Coords(_TestLammpsData_Coords, RefLAMMPSDataMini):
    pass


@pytest.fixture(params=[
    LAMMPSdata,
    LAMMPSdata_mini,
    LAMMPScnt,
    LAMMPShyd,
], scope='module')
def LAMMPSDATAWriter(request, tmpdir_factory):
    filename = request.param
    u = mda.Universe(filename)
    fn = os.path.split(filename)[1]
    outfile = str(tmpdir_factory.mktemp('data').join(fn))

    with mda.Writer(outfile, n_atoms=u.atoms.n_atoms) as w:
        w.write(u.atoms)

    u_new = mda.Universe(outfile)

    return u, u_new


class TestLAMMPSDATAWriter(object):
    def test_Writer_dimensions(self, LAMMPSDATAWriter):
        u_ref, u_new = LAMMPSDATAWriter
        assert_almost_equal(u_ref.dimensions, u_new.dimensions,
                            err_msg="attributes different after writing",
                            decimal=6)
    
    def test_Writer_atoms_types(self, LAMMPSDATAWriter):
        u_ref, u_new = LAMMPSDATAWriter
        assert_equal(u_ref.atoms.types, u_new.atoms.types,
                     err_msg="attributes different after writing",)

    @pytest.mark.parametrize('attr', [
        'bonds', 'angles', 'dihedrals', 'impropers'
    ])
    def test_Writer_atoms(self, attr, LAMMPSDATAWriter):
        u_ref, u_new = LAMMPSDATAWriter
        ref = getattr(u_ref.atoms, attr)
        new = getattr(u_new.atoms, attr)
        assert ref == new, "attributes different after writing"

    @pytest.mark.parametrize('attr', [
        'masses', 'charges', 'velocities', 'positions'
    ])
    def test_Writer_numerical_attrs(self, attr, LAMMPSDATAWriter):
        u_ref, u_new = LAMMPSDATAWriter
        try:
            refvals = getattr(u_ref, attr)
        except (AttributeError):
            with pytest.raises(AttributeError):
                getattr(u_new, attr)
        else:
            assert_almost_equal(refvals,
                                getattr(u_new.atoms, attr),
                                err_msg="attributes different after writing",
                                decimal=6)


def test_datawriter_universe(tmpdir):
    fn = str(tmpdir.join('out.data'))

    u = mda.Universe(LAMMPSdata_mini)

    with mda.Writer(fn, n_atoms=len(u.atoms)) as w:
        w.write(u)

    u2 = mda.Universe(fn)

    assert_almost_equal(u.atoms.positions, u2.atoms.positions)
    assert_almost_equal(u.dimensions, u2.dimensions)


class TestLAMMPSDATAWriter_data_partial(TestLAMMPSDATAWriter):
    N_kept = 5

    @staticmethod
    @pytest.fixture()
    def LAMMPSDATA_partial(tmpdir):
        filename = LAMMPSdata
        N_kept = 5
        u = mda.Universe(filename)
        ext = os.path.splitext(filename)[1]
        outfile = str(tmpdir.join('lammps-data-writer-test' + ext))

        with mda.Writer(outfile, n_atoms=N_kept) as w:
            w.write(u.atoms[:N_kept])

        u_new = mda.Universe(outfile)

        return u, u_new

    @pytest.mark.parametrize('attr', [
        'masses', 'charges', 'velocities', 'positions'
    ])
    def test_Writer_atoms(self, attr, LAMMPSDATA_partial):
        u_ref, u_new = LAMMPSDATA_partial
        if hasattr(u_ref.atoms, attr):
            assert_almost_equal(getattr(u_ref.atoms[:self.N_kept], attr),
                                getattr(u_new.atoms, attr),
                                err_msg="attributes different after writing",
                                decimal=6)
        else:
            with pytest.raises(AttributeError):
                getattr(u_new, attr)

    def test_n_bonds(self, LAMMPSDATA_partial):
        u_ref, u_new = LAMMPSDATA_partial
        assert len(u_new.atoms.bonds) == 4

    def test_n_angles(self, LAMMPSDATA_partial):
        u_ref, u_new = LAMMPSDATA_partial
        assert len(u_new.atoms.angles) == 4


# need more tests of the LAMMPS DCDReader

class TestLAMMPSDCDReader(RefLAMMPSDataDCD):
    flavor = 'LAMMPS'

    @pytest.fixture(scope='class')
    def u(self):
        return mda.Universe(self.topology, self.trajectory,
                            format=self.format)

    def test_Reader_is_LAMMPS(self, u):
        assert u.trajectory.flavor, self.flavor

    def get_frame_from_end(self, offset, u):
        iframe = u.trajectory.n_frames - 1 - offset
        iframe = iframe if iframe > 0 else 0
        return iframe

    def test_n_atoms(self, u):
        assert_equal(u.atoms.n_atoms, self.n_atoms)

    def test_n_frames(self, u):
        assert_equal(u.trajectory.n_frames, self.n_frames)

    def test_dimensions(self, u):
        mean_dimensions = np.mean([ts.dimensions for ts in u.trajectory],
                                  axis=0)
        assert_almost_equal(mean_dimensions, self.mean_dimensions)

    def test_dt(self, u):
        assert_almost_equal(u.trajectory.dt, self.dt,
                            err_msg="Time between frames dt is wrong.")

    def test_Timestep_time(self, u):
        iframe = self.get_frame_from_end(1, u)
        assert_almost_equal(u.trajectory[iframe].time,
                            iframe * self.dt,
                            err_msg="Time for frame {0} (dt={1}) is wrong.".format(
                                iframe, self.dt))

    def test_LAMMPSDCDReader_set_dt(self, u, dt=1500.):
        u = mda.Universe(self.topology, self.trajectory, format=self.format,
                         dt=dt)
        iframe = self.get_frame_from_end(1, u)
        assert_almost_equal(u.trajectory[iframe].time, iframe * dt,
                            err_msg="setting time step dt={0} failed: "
                                    "actually used dt={1}".format(
                                dt, u.trajectory._ts_kwargs['dt']))

    def test_wrong_time_unit(self):
        def wrong_load(unit="nm"):
            return mda.Universe(self.topology, self.trajectory,
                                format=self.format,
                                timeunit=unit)

        with pytest.raises(TypeError):
            wrong_load()

    def test_wrong_unit(self):
        def wrong_load(unit="GARBAGE"):
            return mda.Universe(self.topology, self.trajectory,
                                format=self.format,
                                timeunit=unit)

        with pytest.raises(ValueError):
            wrong_load()


class TestLAMMPSDCDWriter(RefLAMMPSDataDCD):
    flavor = 'LAMMPS'

    @pytest.fixture(scope='class')
    def u(self):
        return mda.Universe(self.topology, self.trajectory, format=self.format)

    def test_Writer_is_LAMMPS(self, u, tmpdir):
        ext = os.path.splitext(self.trajectory)[1]
        outfile = str(tmpdir.join('lammps-writer-test' + ext))
        with mda.Writer(outfile, n_atoms=u.atoms.n_atoms,
                        format=self.format) as W:
            assert W.flavor, self.flavor

    def test_Writer(self, u, tmpdir, n_frames=3):
        ext = os.path.splitext(self.trajectory)[1]
        outfile = str(tmpdir.join('lammps-writer-test' + ext))

        with mda.Writer(outfile,
                        n_atoms=u.atoms.n_atoms,
                        format=self.format) as w:
            for ts in u.trajectory[:n_frames]:
                w.write(u)

        short = mda.Universe(self.topology, outfile)
        assert_equal(short.trajectory.n_frames, n_frames,
                     err_msg="number of frames mismatch")
        assert_almost_equal(short.trajectory[n_frames - 1].positions,
                            u.trajectory[n_frames - 1].positions,
                            6,
                            err_msg="coordinate mismatch between corresponding frames")

    def test_OtherWriter_is_LAMMPS(self, u, tmpdir):
        ext = os.path.splitext(self.trajectory)[1]
        outfile = str(tmpdir.join('lammps-writer-test' + ext))
        with u.trajectory.OtherWriter(outfile) as W:
            assert W.flavor, self.flavor

    def test_OtherWriter(self, u, tmpdir):
        times = []
        ext = os.path.splitext(self.trajectory)[1]
        outfile = str(tmpdir.join('lammps-writer-test' + ext))
        with u.trajectory.OtherWriter(outfile) as w:
            for ts in u.trajectory[::-1]:
                times.append(ts.time)
                w.write(u)
        # note: the reversed trajectory records times in increasing
        #       steps, and NOT reversed, i.e. the time markers are not
        #       attached to their frames. This could be considered a bug
        #       but DCD has no way to store timestamps. Right now, we'll simply
        #       test that this is the case and pass.
        reversed = mda.Universe(self.topology, outfile)
        assert_equal(reversed.trajectory.n_frames, u.trajectory.n_frames,
                     err_msg="number of frames mismatch")
        rev_times = [ts.time for ts in reversed.trajectory]
        assert_almost_equal(rev_times, times[::-1], 6,
                            err_msg="time steps of written DCD mismatch")
        assert_almost_equal(reversed.trajectory[-1].positions,
                            u.trajectory[0].positions,
                            6,
                            err_msg="coordinate mismatch between corresponding frames")


class TestLAMMPSDCDWriterClass(object):
    flavor = 'LAMMPS'

    def test_Writer_is_LAMMPS(self, tmpdir):
        outfile = str(tmpdir.join('lammps-writer-test.dcd'))
        with mda.coordinates.LAMMPS.DCDWriter(outfile, n_atoms=10) as W:
            assert W.flavor, self.flavor

    def test_open(self, tmpdir):
        outfile = str(tmpdir.join('lammps-writer-test.dcd'))
        try:
            with mda.coordinates.LAMMPS.DCDWriter(outfile, n_atoms=10):
                pass
        except Exception:
            pytest.fail()

    def test_wrong_time_unit(self, tmpdir):
        outfile = str(tmpdir.join('lammps-writer-test.dcd'))
        with pytest.raises(TypeError):
            with mda.coordinates.LAMMPS.DCDWriter(outfile, n_atoms=10,
                                                  timeunit='nm'):
                pass

    def test_wrong_unit(self, tmpdir):
        outfile = str(tmpdir.join('lammps-writer-test.dcd'))
        with pytest.raises(ValueError):
            with mda.coordinates.LAMMPS.DCDWriter(outfile, n_atoms=10,
                                                  timeunit='GARBAGE'):
                pass


def test_triclinicness():
    u = mda.Universe(LAMMPScnt)

    assert u.dimensions[3] == 90.
    assert u.dimensions[4] == 90.
    assert u.dimensions[5] == 120.


@pytest.fixture
def tmpout(tmpdir):
    return str(tmpdir.join('out.data'))


class TestDataWriterErrors(object):
    def test_write_no_masses(self, tmpout):
        u = make_Universe(('types',), trajectory=True)

        try:
            u.atoms.write(tmpout)
        except NoDataError as e:
            assert 'masses' in e.args[0]
        else:
            pytest.fail()

    def test_write_no_types(self, tmpout):
        u = make_Universe(('masses',), trajectory=True)

        try:
            u.atoms.write(tmpout)
        except NoDataError as e:
            assert 'types' in e.args[0]
        else:
            pytest.fail()

    def test_write_non_numerical_types(self, tmpout):
        u = make_Universe(('types', 'masses'), trajectory=True)

        try:
            u.atoms.write(tmpout)
        except ValueError as e:
            assert 'must be convertible to integers' in e.args[0]
        else:
            raise pytest.fail()


class TestLammpsDumpReader(object):
    @pytest.fixture(
        params=['ascii', 'bz2', 'gzip']
    )
    def u(self, tmpdir, request):
        trjtype = request.param
        if trjtype == 'bz2':
            # no conversion needed
            f = LAMMPSDUMP
        else:
            f = str(tmpdir.join('lammps.' + trjtype))
            with bz2.BZ2File(LAMMPSDUMP, 'rb') as datain:
                data = datain.read()
            if trjtype == 'ascii':
                with open(f, 'wb') as fout:
                    fout.write(data)
            elif trjtype == 'gzip':
                with gzip.GzipFile(f, 'wb') as fout:
                    fout.write(data)

        yield mda.Universe(f, format='LAMMPSDUMP',
                           lammps_coordinate_convention="auto")

    @pytest.fixture()
    def reference_positions(self):
        # manually copied from traj file
        data = {}

        # at timestep 500
        lo, hi = float(2.1427867124774069e-01), float(5.9857213287522608e+00)
        length1 = hi - lo
        # at timestep 1000
        lo, hi = float(-5.4458069063278991e-03), float(6.2054458069063330e+00)
        length2 = hi - lo
        boxes = [
            np.array([6.2, 6.2, 6.2, 90., 90., 90.]),
            np.array([length1, length1, length1, 90., 90., 90.]),
            np.array([length2, length2, length2, 90., 90., 90.]),
        ]
        data['box'] = boxes

        # data for atom id 1 in traj (ie first in frame)
        # isn't sensitive to required sorting
        atom1_pos1 = np.array([0.25, 0.25, 0.241936]) * boxes[0][:3]
        atom1_pos2 = np.array([0.278215, 0.12611, 0.322087]) * boxes[1][:3]
        atom1_pos3 = np.array([0.507123, 1.00424, 0.280972]) * boxes[2][:3]
        data['atom1_pos'] = [atom1_pos1, atom1_pos2, atom1_pos3]
        # data for atom id 13
        # *is* sensitive to reordering of positions
        # normally appears 4th in traj data
        atom13_pos1 = np.array([0.25, 0.25, 0.741936]) * boxes[0][:3]
        atom13_pos2 = np.array([0.394618, 0.263115, 0.798295]) * boxes[1][:3]
        atom13_pos3 = np.array([0.332363, 0.30544, 0.641589]) * boxes[2][:3]
        data['atom13_pos'] = [atom13_pos1, atom13_pos2, atom13_pos3]

        return data

    def test_n_atoms(self, u):
        assert len(u.atoms) == 24

    def test_length(self, u):
        assert len(u.trajectory) == 3
        for i, ts in enumerate(u.trajectory):
            assert ts.frame == i
            assert ts.data['step'] == i * 500
        for i, ts in enumerate(u.trajectory):
            assert ts.frame == i
            assert ts.data['step'] == i * 500

    def test_seeking(self, u, reference_positions):
        u.trajectory[1]

        assert_almost_equal(u.dimensions, reference_positions['box'][1],
                            decimal=5)
        assert_almost_equal(u.atoms[0].position,
                            reference_positions['atom1_pos'][1],
                            decimal=5)
        assert_almost_equal(u.atoms[12].position,
                            reference_positions['atom13_pos'][1],
                            decimal=5)

    def test_boxsize(self, u, reference_positions):
        for ts, box in zip(u.trajectory,
                           reference_positions['box']):
            assert_almost_equal(ts.dimensions, box, decimal=5)

    def test_atom_reordering(self, u, reference_positions):
        atom1 = u.atoms[0]
        atom13 = u.atoms[12]
        for ts, atom1_pos, atom13_pos in zip(u.trajectory,
                                             reference_positions['atom1_pos'],
                                             reference_positions['atom13_pos']):
            assert_almost_equal(atom1.position, atom1_pos, decimal=5)
            assert_almost_equal(atom13.position, atom13_pos, decimal=5)


@pytest.mark.parametrize("convention",["unscaled","unwrapped","scaled_unwrapped"])
def test_open_absent_convention_fails(convention):
    with pytest.raises(ValueError, match="no coordinate information of type"):
        mda.Universe(LAMMPSDUMP, format='LAMMPSDUMP',
                       lammps_coordinate_convention=convention)

def test_open_incorrect_convention_fails():
    with pytest.raises(ValueError, match="coordinate convention incorrectly specified"):
        mda.Universe(LAMMPSDUMP, format='LAMMPSDUMP',
                       lammps_coordinate_convention="42")


@pytest.mark.parametrize("convention",["auto", "unscaled", "scaled",
                         "unwrapped","scaled_unwrapped"])
def test_open_all_convention(convention):
    mda.Universe(LAMMPSDUMP_allcoords, format='LAMMPSDUMP',
                       lammps_coordinate_convention=convention)

class TestCoordinateMatches(object):
    @pytest.fixture()
    def universes(self):
        coordinate_conventions = ["auto","unscaled", "scaled", "unwrapped",
                    "scaled_unwrapped"]
        universes = {i: mda.Universe(LAMMPSDUMP_allcoords, format='LAMMPSDUMP',
                       lammps_coordinate_convention=i) for i in coordinate_conventions}
        return universes
    
    @pytest.fixture()
    def reference_unscaled_positions(self):
        # copied from trajectory file
        # atom 340 is the first one in the trajectory so we use that
        atom340_pos1_unscaled = [4.48355, 0.331422, 1.59231]
        atom340_pos2_unscaled = [4.41947, 35.4403, 2.25115]
        atom340_pos3_unscaled = [4.48989, 0.360633, 2.63623]
        return np.asarray([atom340_pos1_unscaled, atom340_pos2_unscaled,atom340_pos3_unscaled])
    
    def test_unscaled_reference(self, universes, reference_unscaled_positions):
        atom_340 = universes["unscaled"].atoms[339]
        for i,ts_u in enumerate(universes["unscaled"].trajectory[0:3]):
            assert_almost_equal(atom_340.position, reference_unscaled_positions[i,:], decimal=5)
    
    def test_scaled_reference(self, universes, reference_unscaled_positions):
        # NOTE use of unscaled positions here due to S->R transform
        atom_340 = universes["scaled"].atoms[339]
        for i,ts_u in enumerate(universes["scaled"].trajectory[0:3]):
            assert_almost_equal(atom_340.position, reference_unscaled_positions[i,:], decimal=1)
            # NOTE this seems a bit inaccurate?

    @pytest.fixture()
    def reference_unwrapped_positions(self):
        # copied from trajectory file
        # atom 340 is the first one in the trajectory so we use that
        atom340_pos1_unwrapped = [4.48355, 35.8378, 1.59231]
        atom340_pos2_unwrapped = [4.41947, 35.4403, 2.25115]
        atom340_pos3_unwrapped = [4.48989, 35.867, 2.63623]
        return np.asarray([atom340_pos1_unwrapped, atom340_pos2_unwrapped, atom340_pos3_unwrapped])

    def test_unwrapped_scaled_reference(self, universes, reference_unwrapped_positions):
        atom_340 = universes["unwrapped"].atoms[339]
        for i,ts_u in enumerate(universes["unwrapped"].trajectory[0:3]):
            assert_almost_equal(atom_340.position, reference_unwrapped_positions[i,:], decimal=5)

    def test_unwrapped_scaled_reference(self, universes, reference_unwrapped_positions):
        # NOTE use of unscaled positions here due to S->R transform
        atom_340 = universes["scaled_unwrapped"].atoms[339]
        for i,ts_u in enumerate(universes["scaled_unwrapped"].trajectory[0:3]):
            assert_almost_equal(atom_340.position, reference_unwrapped_positions[i,:], decimal=1)
            # NOTE this seems a bit inaccurate?
    
    def test_scaled_unscaled_match(self, universes):
        assert(len(universes["unscaled"].trajectory)== len(universes["scaled"].trajectory))
        for ts_u,ts_s in zip(universes["unscaled"].trajectory, universes["scaled"].trajectory):
            assert_almost_equal(ts_u.positions, ts_s.positions,decimal=1)
            # NOTE this seems a bit inaccurate?

    def test_unwrapped_scaled_unwrapped_match(self, universes):
        assert(len(universes["unwrapped"].trajectory)== len(universes["scaled_unwrapped"].trajectory))
        for ts_u,ts_s in zip(universes["unwrapped"].trajectory, universes["scaled_unwrapped"].trajectory):
            assert_almost_equal(ts_u.positions, ts_s.positions,decimal=1)
            # NOTE this seems a bit inaccurate?
    
    def test_auto_is_unscaled_match(self, universes):
        assert(len(universes["auto"].trajectory)== len(universes["unscaled"].trajectory))
        for ts_u,ts_s in zip(universes["auto"].trajectory, universes["unscaled"].trajectory):
            assert_almost_equal(ts_u.positions, ts_s.positions,decimal=5)
