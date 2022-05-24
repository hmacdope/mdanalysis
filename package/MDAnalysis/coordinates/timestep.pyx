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
#

import weakref
import warnings
import copy
import numbers

import numpy as np
cimport numpy as cnp
cnp.import_array()

from libc.stdint cimport uint64_t
from libcpp cimport bool

from . import core
from .. import NoDataError
from .. import (
    _READERS, _READER_HINTS,
    _SINGLEFRAME_WRITERS,
    _MULTIFRAME_WRITERS,
    _CONVERTERS
)
from .. import units
from ..auxiliary.base import AuxReader
from ..auxiliary.core import auxreader
from ..lib.util import asiterable, Namespace

cdef class Timestep:

    order = 'C'

    cdef public uint64_t n_atoms
    cdef public uint64_t frame 


    cdef bool _has_positions
    cdef bool _has_velocities
    cdef bool _has_forces

    cdef cnp.ndarray _dimensions
    cdef cnp.ndarray _positions
    cdef cnp.ndarray _velocities
    cdef cnp.ndarray _forces

    cdef object _dtype
    cdef public dict data
    cdef public object aux




    def __cinit__(self, uint64_t n_atoms, dtype=np.float32, **kwargs):
        # c++ level objects
        self.n_atoms =  n_atoms
        self.frame = -1
        self._has_positions = False
        self._has_velocities = False
        self._has_forces = False

        # match original can this be removed?
        self._dimensions = np.zeros(6, dtype=np.float32)

    def __init__(self, uint64_t n_atoms, dtype=np.float32, **kwargs):
        #python objects
        self._dtype = dtype
        self.data = {}

        for att in ('dt', 'time_offset'):
            try:
                self.data[att] = kwargs[att]
            except KeyError:
                pass
        try:
            # do I have a hook back to the Reader?
            self._reader = weakref.ref(kwargs['reader'])
        except KeyError:
            pass

        self.has_positions = kwargs.get('positions', True)
        self.has_velocities = kwargs.get('velocities', False)
        self.has_forces = kwargs.get('forces', False)

        # set up aux namespace for adding auxiliary data
        self.aux = Namespace()
        
    
    def __dealloc__(self):
            pass

    @property
    def dtype(self):
        return self._dtype


    @property
    def has_positions(self):
        return self._has_positions

    @has_positions.setter
    def has_positions(self, val):
        if val and not self._has_positions:
            # Setting this will always reallocate position data
            # ie
            # True -> False -> True will wipe data from first True state
            self._positions = np.zeros((self.n_atoms, 3), dtype=self.dtype,
                                 order=self.order)
            self._has_positions = True
        elif not val:
            # Unsetting val won't delete the numpy array
            self._has_positions = False

    
    @property
    def has_velocities(self):
        return self._has_velocities

    @has_velocities.setter
    def has_velocities(self, val):
        if val and not self._has_velocities:
            # Setting this will always reallocate velocity data
            # ie
            # True -> False -> True will wipe data from first True state
            self._velocities = np.zeros((self.n_atoms, 3), dtype=self.dtype,
                                 order=self.order)
            self._has_velocities = True
        elif not val:
            # Unsetting val won't delete the numpy array
            self._has_velocities = False
    
    @property
    def has_forces(self):
        return self._has_forces

    @has_forces.setter
    def has_forces(self, val):
        if val and not self._has_forces:
            # Setting this will always reallocate force data
            # ie
            # True -> False -> True will wipe data from first True state
            self._forces = np.zeros((self.n_atoms, 3), dtype=self.dtype,
                                 order=self.order)
            self._has_forces = True
        elif not val:
            # Unsetting val won't delete the numpy array
            self._has_forces = False


    @property
    def positions(self):
        if self._has_positions:
            return self._positions
        else:
            raise NoDataError("This Timestep has no position information")

 
    @positions.setter
    def positions(self,  cnp.ndarray new_positions):
        # force C contig memory order
        self._positions = new_positions
        self._has_positions = True



    @property
    def _x(self):
        """A view onto the x dimension of position data

        .. versionchanged:: 0.11.0
           Now read only
        """
        return self.positions[:, 0]

    @property
    def _y(self):
        """A view onto the y dimension of position data

        .. versionchanged:: 0.11.0
           Now read only
        """
        return self.positions[:, 1]

    @property
    def _z(self):
        """A view onto the z dimension of position data

        .. versionchanged:: 0.11.0
           Now read only
        """
        return self.positions[:, 2]

    @property
    def dimensions(self):
        """View of unitcell dimensions (*A*, *B*, *C*, *alpha*, *beta*, *gamma*)

        lengths *a*, *b*, *c* are in the MDAnalysis length unit (Å), and
        angles are in degrees.
        """
        if (self._dimensions[:3] == 0).all():
            return None
        else:
            return self._dimensions

    @dimensions.setter
    def dimensions(self, cnp.ndarray new_dimensions):
        if new_dimensions is None:
            self._dimensions[:] = 0
        else:
            self._dimensions[:] = np.ascontiguousarray(new_dimensions).copy()

    
    @property
    def volume(self):
        """volume of the unitcell"""
        if self.dimensions is None:
            return 0
        else:
            return core.box_volume(self.dimensions)

    @property
    def triclinic_dimensions(self):
        """The unitcell dimensions represented as triclinic vectors

        Returns
        -------
        numpy.ndarray
             A (3, 3) numpy.ndarray of unit cell vectors

        Examples
        --------
        The unitcell for a given system can be queried as either three
        vectors lengths followed by their respective angle, or as three
        triclinic vectors.

          >>> ts.dimensions
          array([ 13.,  14.,  15.,  90.,  90.,  90.], dtype=float32)
          >>> ts.triclinic_dimensions
          array([[ 13.,   0.,   0.],
                 [  0.,  14.,   0.],
                 [  0.,   0.,  15.]], dtype=float32)

        Setting the attribute also works::

          >>> ts.triclinic_dimensions = [[15, 0, 0], [5, 15, 0], [5, 5, 15]]
          >>> ts.dimensions
          array([ 15.        ,  15.81138802,  16.58312416,  67.58049774,
                  72.45159912,  71.56504822], dtype=float32)

        See Also
        --------
        :func:`MDAnalysis.lib.mdamath.triclinic_vectors`


        .. versionadded:: 0.11.0
        """
        if self.dimensions is None:
            return None
        else:
            return core.triclinic_vectors(self.dimensions)

    @triclinic_dimensions.setter
    def triclinic_dimensions(self, new):
        """Set the unitcell for this Timestep as defined by triclinic vectors

        .. versionadded:: 0.11.0
        """
        if new is None:
            self.dimensions = None
        else:
            self.dimensions = core.triclinic_box(*new)

    @property
    def velocities(self):
        if self._has_velocities:
            return self._velocities
        else:
            raise NoDataError("This Timestep has no velocities information")


 
    @velocities.setter
    def velocities(self,  cnp.ndarray new_velocities):
        # force C contig memory order
        self._velocities[:,:] = np.ascontiguousarray(new_velocities).copy()
        self._has_velocities = True


    @property
    def forces(self):
        if self._has_forces:
          return self._forces
        else:
            raise NoDataError("This Timestep has no force information")


 
    @forces.setter
    def forces(self,  cnp.ndarray new_forces):
        # force C contig memory order
        self._forces[:,:] = np.ascontiguousarray(new_forces).copy()
        self._has_forces = True



    @classmethod
    def from_timestep(cls, other, **kwargs):
        """Create a copy of another Timestep, in the format of this Timestep

        .. versionadded:: 0.11.0
        """
        ts = cls(other.n_atoms,
                 positions=other.has_positions,
                 velocities=other.has_velocities,
                 forces=other.has_forces,
                 **kwargs)
        ts.frame = other.frame
        if  other.dimensions:
            ts.dimensions = other.dimensions.copy(order=cls.order)
        try:
            ts.positions = other.positions.copy(order=cls.order)
        except NoDataError:
            pass
        try:
            ts.velocities = other.velocities.copy(order=cls.order)
        except NoDataError:
            pass
        try:
            ts.forces = other.forces.copy(order=cls.order)
        except NoDataError:
            pass

        # Optional attributes that don't live in .data
        # should probably iron out these last kinks
        for att in ('_frame',):
            try:
                setattr(ts, att, getattr(other, att))
            except AttributeError:
                pass

        if hasattr(ts, '_reader'):
            other._reader = weakref.ref(ts._reader())

        ts.data = copy.deepcopy(other.data)

        return ts

    @classmethod
    def from_coordinates(cls,
                         positions=None,
                         velocities=None,
                         forces=None,
                         **kwargs):
        """Create an instance of this Timestep, from coordinate data

        Can pass position, velocity and force data to form a Timestep.

        .. versionadded:: 0.11.0
        """
        has_positions = positions is not None
        has_velocities = velocities is not None
        has_forces = forces is not None

        lens = [len(a) for a in [positions, velocities, forces]
                if a is not None]
        if not lens:
            raise ValueError("Must specify at least one set of data")
        n_atoms = max(lens)
        # Check arrays are matched length?
        if not all(val == n_atoms for val in lens):
            raise ValueError("Lengths of input data mismatched")

        ts = cls(n_atoms,
                 positions=has_positions,
                 velocities=has_velocities,
                 forces=has_forces,
                 **kwargs)
        if has_positions:
            ts.positions = positions
        if has_velocities:
            ts.velocities = velocities
        if has_forces:
            ts.forces = forces

        return ts


    def __getstate__(self):
        #  The `dt` property is lazy loaded.
        #  We need to load it once from the `_reader` (if exists)
        #  attached to this timestep to get the dt value.
        #  This will help to (un)pickle a `Timestep` without pickling `_reader`
        #  and retain its dt value.
        self.dt

        state = self.__dict__.copy()
        state.pop('_reader', None)

        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __eq__(self, other):
        """Compare with another Timestep

        .. versionadded:: 0.11.0
        """
        if not isinstance(other, Timestep):
            return False

        if not self.frame == other.frame:
            return False

        if not self.n_atoms == other.n_atoms:
            return False

        if not self.has_positions == other.has_positions:
            return False
        if self.has_positions:
            if not (self.positions == other.positions).all():
                return False

        if self.dimensions is None:
            if other.dimensions is not None:
                return False
        else:
            if other.dimensions is None:
                return False
            if not (self.dimensions == other.dimensions).all():
                return False

        if not self.has_velocities == other.has_velocities:
            return False
        if self.has_velocities:
            if not (self.velocities == other.velocities).all():
                return False

        if not self.has_forces == other.has_forces:
            return False
        if self.has_forces:
            if not (self.forces == other.forces).all():
                return False

        return True

    def __ne__(self, other):
        return not self == other

    def __getitem__(self, atoms):
        """Get a selection of coordinates

        ``ts[i]``

           return coordinates for the i'th atom (0-based)

        ``ts[start:stop:skip]``

           return an array of coordinates, where start, stop and skip
           correspond to atom indices,
           :attr:`MDAnalysis.core.groups.Atom.index` (0-based)
        """
        if isinstance(atoms, numbers.Integral):
            return self._pos[atoms]
        elif isinstance(atoms, (slice, np.ndarray)):
            return self._pos[atoms]
        else:
            raise TypeError

    def __getattr__(self, attr):
        # special-case timestep info
        if attr in ('velocities', 'forces', 'positions'):
            raise NoDataError('This Timestep has no ' + attr)
        err = "{selfcls} object has no attribute '{attr}'"
        raise AttributeError(err.format(selfcls=type(self).__name__,
                                        attr=attr))

    def __len__(self):
        return self.n_atoms

    def __iter__(self):
        """Iterate over coordinates

        ``for x in ts``

            iterate of the coordinates, atom by atom
        """
        for i in range(self.n_atoms):
            yield self[i]

    def __repr__(self):
        desc = "< Timestep {0}".format(self.frame)
        try:
            tail = " with unit cell dimensions {0} >".format(self.dimensions)
        except NotImplementedError:
            tail = " >"
        return desc + tail

    def copy(self):
        """Make an independent ("deep") copy of the whole :class:`Timestep`."""
        return self.__deepcopy__()

    def __deepcopy__(self):
        return self.from_timestep(self)

    def copy_slice(self, sel):
        """Make a new `Timestep` containing a subset of the original `Timestep`.

        Parameters
        ----------
        sel : array_like or slice
            The underlying position, velocity, and force arrays are sliced
            using a :class:`list`, :class:`slice`, or any array-like.

        Returns
        -------
        :class:`Timestep`
            A `Timestep` object of the same type containing all header
            information and all atom information relevant to the selection.

        Note
        ----
        The selection must be a 0 based :class:`slice` or array of the atom indices
        in this :class:`Timestep`

        Example
        -------
        Using a Python :class:`slice` object::

           new_ts = ts.copy_slice(slice(start, stop, step))

        Using a list of indices::

           new_ts = ts.copy_slice([0, 2, 10, 20, 23])


        .. versionadded:: 0.8
        .. versionchanged:: 0.11.0
           Reworked to follow new Timestep API.  Now will strictly only
           copy official attributes of the Timestep.

        """
        # Detect the size of the Timestep by doing a dummy slice
        try:
            pos = self.positions[sel, :]
        except NoDataError:
            # It's cool if there's no Data, we'll live
            pos = None
        except Exception:
            errmsg = ("Selection type must be compatible with slicing the "
                      "coordinates")
            raise TypeError(errmsg) from None
        try:
            vel = self.velocities[sel, :]
        except NoDataError:
            vel = None
        except Exception:
            errmsg = ("Selection type must be compatible with slicing the "
                      "coordinates")
            raise TypeError(errmsg) from None
        try:
            force = self.forces[sel, :]
        except NoDataError:
            force = None
        except Exception:
            errmsg = ("Selection type must be compatible with slicing the "
                      "coordinates")
            raise TypeError(errmsg) from None

        new_TS = self.__class__.from_coordinates(
            positions=pos,
            velocities=vel,
            forces=force)

        new_TS.dimensions = self.dimensions

        new_TS.frame = self.frame

        for att in ('_frame',):
            try:
                setattr(new_TS, att, getattr(self, att))
            except AttributeError:
                pass

        if hasattr(self, '_reader'):
            new_TS._reader = weakref.ref(self._reader())

        new_TS.data = copy.deepcopy(self.data)

        return new_TS



    @property
    def dt(self):
        """The time difference in ps between timesteps

        Note
        ----
        This defaults to 1.0 ps in the absence of time data


        .. versionadded:: 0.11.0
        """
        try:
            return self.data['dt']
        except KeyError:
            pass
        try:
            dt = self.data['dt'] = self._reader()._get_dt()
            return dt
        except AttributeError:
            pass
        warnings.warn("Reader has no dt information, set to 1.0 ps")
        return 1.0
    @dt.setter
    def dt(self, new):
        self.data['dt'] = new

    @dt.deleter
    def dt(self):
        del self.data['dt']

    @property
    def time(self):
        """The time in ps of this timestep

        This is calculated as::

          time = ts.data['time_offset'] + ts.time

        Or, if the trajectory doesn't provide time information::

          time = ts.data['time_offset'] + ts.frame * ts.dt

        .. versionadded:: 0.11.0
        """
        offset = self.data.get('time_offset', 0)
        try:
            return self.data['time'] + offset
        except KeyError:
            return self.dt * self.frame + offset

    @time.setter
    def time(self, new):
        self.data['time'] = new

    @time.deleter
    def time(self):
        del self.data['time']
    