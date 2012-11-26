######################################################
#
#  BioSignalML Management in Python
#
#  Copyright (c) 2010-2011  David Brooks
#
#  $ID: c1bb582 on Tue May 1 10:48:29 2012 +1200 by Dave Brooks $
#
######################################################

import math
import logging

import biosignalml.rdf as rdf
from biosignalml import BSML
from biosignalml.formats import BSMLRecording, BSMLSignal
from biosignalml.data import DataSegment, UniformTimeSeries, TimeSeries, Clock, UniformClock

from h5recording import H5Recording


class HDF5Signal(BSMLSignal):
#============================

  def __init__(self, uri, units, **kwds):
  #--------------------------------------
    BSMLSignal.__init__(self, uri, units, **kwds)
    self._h5 = None

  def __len__(self):
  #-----------------
    return len(self._h5) if self._h5 is not None else 0

  def _set_h5_signal(self, h5):
  #----------------------------
    self._h5 = h5
    if   h5.clock: self.clock = Clock(h5.clock.uri, h5.clock)
    elif h5.rate:  self.clock = UniformClock(None, h5.rate)

  @classmethod
  def create_from_H5Signal(cls, index, signal):
  #--------------------------------------------
    self = cls(signal.uri, signal.units, rate=signal.rate, clock=signal.clock)
    self._set_h5_signal(signal)
    return self

  def read(self, interval=None, segment=None, maxduration=None, maxpoints=None):
  #-----------------------------------------------------------------------------
    """
    Read data from a Signal.

    :param interval: The portion of the signal to read.
    :type interval: :class:`~biosignaml.time.Interval`
    :param segment: A 2-tuple with start and finishing data indices, with the end
      point not included in the returned range.
    :param maxduration: The maximum duration, in seconds, of a single returned segment.
    :param maxpoints: The maximum length, in samples, of a single returned segment.
    :return: An `iterator` returning :class:`~biosignalml.data.DataSegment` segments
      of the signal data.

    If both ``maxduration`` and ``maxpoints`` are given their minimum value is used.
    """

    if   interval is not None and segment is not None:
      raise ValueError("'interval' and 'segment' cannot both be specified")
    if maxduration:
      pts = int(self.rate*maxduration + 0.5)
      if maxpoints: maxpoints = min(maxpoints, pts)
      else: maxpoints = pts
    if maxpoints is None or not (0 < maxpoints <= BSMLSignal.MAXPOINTS):
      maxpoints = BSMLSignal.MAXPOINTS

    # We need to be consistent as to what an interval is....
    # Use model.Interval ??
    if interval is not None:
      segment = (self.clock.index(interval.start), self.clock.index(interval.end))

    if segment is None:
      startpos = 0
      length = len(self)
    else:
      if segment[0] <= segment[1]: seg = segment
      else:                        seg = (segment[1], segment[0])
      ##startpos = max(0, int(math.floor(seg[0])))
      startpos = max(0, seg[0])
      length = min(len(self), seg[1]+1) - startpos

    while length > 0:
      if maxpoints > length: maxpoints = length
      data = self._h5[startpos: startpos+maxpoints]
      if isinstance(self.clock, UniformClock):
        yield DataSegment(self.clock[startpos], UniformTimeSeries(data, self.clock.rate))
      else:
        yield DataSegment(0, TimeSeries(self.clock[startpos: startpos+maxpoints], data))
      startpos += len(data)
      length -= len(data)

  def initialise(self):
  #--------------------
    self._set_h5_signal(self.recording._h5.get_signal(self.uri))

  def append(self, timeseries):
  #----------------------------
    '''
    Append data to a Signal.

    :param timeseries: The data points (and times) to append.
    :type timeseries: :class:`~biosignalml.data.TimeSeries`
    '''
    if self.clock and not isinstance(self.clock, UniformClock):
      self.recording._h5.extend_clock(self.clock.uri, timeseries.time.times)
    self.recording._h5.extend_signal(self.uri, timeseries.data)


class HDF5Recording(BSMLRecording):
#==================================

  MIMETYPE = 'application/x-bsml+hdf5'
  EXTENSIONS = [ 'h5', 'hdf', 'hdf5' ]
  SignalClass = HDF5Signal

  def __init__(self, uri, dataset=None, **kwds):
  #---------------------------------------------
    ## What about self.load_metadata() ???? Do kwds override ??
    BSMLRecording.__init__(self, uri, dataset, **kwds)
    if dataset:
      self._h5 = self._openh5(dataset)
      if uri is not None and str(uri) != str(self._h5.uri):
        raise TypeError("Wrong URI in HDF5 recording")
      ## What about self.load_metadata() ???? Do kwds override ??
      for n, s in enumerate(self._h5.signals()):
        self.add_signal(HDF5Signal.create_from_H5Signal(n, s))
    else:
      self._h5 = None

  def _openh5(self, fname):
  #------------------------
    try:            return H5Recording.open(fname)
    except IOError: return H5Recording.create(self.uri, fname)

  @classmethod
  def open(cls, dataset):
  #----------------------
    return cls(None, dataset)

  def close(self):
  #---------------
    if self._h5:
      self._h5.close()
      self._h5 = None

  def new_signal(self, uri, units, id=None, **kwds):
  #-------------------------------------------------
    '''
    Create a new Signal and add it to the Recording.

    :param uri: The URI for the signal.
    :param units: The units signal values are in.
    :rtype: :class:`HDF5Signal`
    '''
    sig = BSMLRecording.new_signal(self, uri, units, id=id, **kwds)
    if self._h5:
      if sig.clock: self._h5.create_clock(sig.clock.uri)
      sig._h5 = self._h5.create_signal(sig.uri, units, rate=sig.rate, clock=sig.clock)
    return sig

  def save_metadata(self, format=rdf.Format.TURTLE, prefixes=None):
  #----------------------------------------------------------------
    self._h5.store_metadata(self.metadata_as_string(format=format, prefixes=prefixes),
                        rdf.Format.mimetype(format))

  def load_metadata(self):
  #-----------------------
    rdf, format = self._h5,get_metadata()
    if rdf:
      self.load_from_graph(rdf.Graph.create_from_string(self.uri, rdf, format))

  def initialise(self, **kwds):
  #----------------------------
    if self.dataset is not None:
      self._h5 = self._openh5(str(self.dataset))
      for s in self.signals():
        HDF5Signal.initialise_class(s)

