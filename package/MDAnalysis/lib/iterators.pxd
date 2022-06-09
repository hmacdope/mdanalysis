from libcpp.vector cimport vector
from libc.stdint cimport uint64_t

cdef extern from "iterators.h":
    cdef cppclass _IteratorBase:
        uint64_t n_atoms
        vector[uint64_t] ix
        uint64_t i
        float *ptr
        _IteratorBase()
        _IteratorBase(uint64_t n_atoms)
        void load_into_external_buffer(float *buffer, uint64_t n_idx)



cdef extern from "iterators.h":
    cdef cppclass _AtomGroupIterator(_IteratorBase):
        _AtomGroupIterator()
        _AtomGroupIterator(uint64_t n_atoms) 


cdef extern from "iterators.h":
    cdef cppclass _ArrayIterator(_IteratorBase):
        _ArrayIterator()
        _ArrayIterator(uint64_t n_atoms) 