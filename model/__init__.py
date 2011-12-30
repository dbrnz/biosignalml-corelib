######################################################
#
#  BioSignalML Management in Python
#
#  Copyright (c) 2010-2011  David Brooks
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#  $ID: bbd3c04 on Wed Jun 8 16:47:09 2011 +1200 by Dave Brooks $
#
######################################################


"""
An abstract model for BioSignalML.

"""

import uuid
import logging

from biosignalml.bsml import BSML
from biosignalml.metadata import NAMESPACES
from biosignalml.metadata import RDF, TL, EVT
from biosignalml.rdfmodel import Uri, Statement, Graph

from mapping import bsml_mapping
from data import TimeSeries


class Metadata(object):
#======================

  metaclass = None

  attributes = [ 'uri', 'description' ]

  def __init__(self, uri, metadata={}):
  #----------------------------------
    self.metadata = { }
    self.set_metavars(metadata)
    self.uri = Uri(uri)

  def set_metavars(self, meta):
  #----------------------------
    for cls in self.__class__.__mro__:
      if 'attributes' in cls.__dict__:
        for attr in cls.__dict__['attributes']:
          setattr(self, attr, meta.get(attr, None))

  def get_metavars(self):
  #----------------------
    metadata = { }
    for cls in self.__class__.__mro__:
      if 'attributes' in cls.__dict__:
        for attr in cls.__dict__['attributes']:
          value = getattr(self, attr, None)
          if value is not None: metadata[attr] = value
    return metadata

  def makeuri(self, sibling=False):
  #--------------------------------
    u = str(self.uri)
    if   u.endswith(('/', '#')): return '%s%s'  % (u, uuid.uuid1())
    elif sibling:
      slash = u.rfind('/')
      hash  = u.rfind('#')
      if hash > slash:           return '%s#%s' % (u.rsplit('#', 1)[0], uuid.uuid1())
      else:                      return '%s/%s' % (u.rsplit('/', 1)[0], uuid.uuid1())
    else:                        return '%s/%s' % (u, uuid.uuid1())

  def map_to_graph(self, graph, rdfmap=None):
  #------------------------------------------
    if rdfmap is None: rdfmap = bsml_mapping()
    if (self.metaclass):
      graph.append(Statement(self.uri, RDF.type, self.metaclass))
      graph.add_statements(rdfmap.statement_stream(self))

  def _assign(self, attr, value):
  #------------------------------
    if attr in self.__dict__: setattr(self, attr, value)
    else:                     self.metadata[attr] = value

  @classmethod
  def create_from_repository(cls, uri, repo, rdfmap=None, **kwds):
  #---------------------------------------------------------------
    if rdfmap is None: rdfmap = bsml_mapping()
    self = cls(uri, **kwds)
    statements = repo.statements('<%(uri)s> ?p ?o',
                                  '<%(uri)s> a  <%(type)s> . <%(uri)s> ?p ?o',
                                  { 'uri': str(uri), 'type': str(self.metaclass) })
    for stmt in statements:
      s, attr, v = rdfmap.metadata(stmt, self.metaclass)
      ##logging.debug("%s='%s'", attr, v)
      self._assign(attr, v)
    return self

  def set_from_graph(self, attr, graph, rdfmap=None):
  #--------------------------------------------------
    if rdfmap is None: rdfmap = bsml_mapping()
    v = rdfmap.get_value_from_graph(self.uri, attr, graph)
    if v: self._assign(attr, v)


class Recording(Metadata):
#=========================

  metaclass = BSML.Recording

  attributes = [ 'label', 'source', 'format', 'comment', 'investigation',
                 'starttime', 'duration',
               ]

  def __init__(self, uri, metadata={}):
  #------------------------------------
    super(Recording, self).__init__(uri, metadata=metadata)
    self.timeline = RelativeTimeLine(str(uri) + '/timeline')
    self._signals = { }
    self._signal_uris = [ ]
    self._events = { }

  def load_signals_from_repository(self, repo, rdfmap=None):
  #---------------------------------------------------------
    for sig in repo.get_subjects(BSML.recording, self.uri):
      self.add_signal(Signal.create_from_repository(sig, repo, rdfmap))

  def signals(self):
  #-----------------
    return [ self._signals[s] for s in sorted(self._signal_uris) ]

  def add_signal(self, signal):
  #----------------------------
    """Add a :class:`Signal` to a Recording.

    :param signal: The signal to add to the recording.
    :type signal: :class:`Signal`
    :return: The 1-origin index of the signal in the recording.
    """
    logging.debug("Adding signal: %s", signal.uri)
    if signal.uri in self._signal_uris:
      raise Exception, "Signal '%s' already in recording" % signal.uri
    if signal.recording and str(signal.recording) != str(self.uri):  ## Set from RDF mapping...
      raise Exception, "Signal '%s' is in Recording '%s'" % (signal.uri, signal.recording)
    signal.recording = self
    self._signal_uris.append(str(signal.uri))
    self._signals[str(signal.uri)] = signal
    return len(self._signal_uris) - 1         # 0-origin index of newly added signal uri

  def get_signal(self, uri=None, index=0):
  #---------------------------------------
    """Retrieve a :class:`Signal` from a Recording.

    :param uri: The uri of the signal to get.
    :param index: The 1-origin index of the signal to get.
    :return: A signal in the recording.
    :rtype: :class:`Signal`
    """
    if uri is None: uri = self._signal_uris[index]
    return self._signals[str(uri)]

  def __len__(self):
  #-----------------
    return len(self._signals)


  def events(self):
  #-----------------
    return self._events.itervalues()

  def add_event(self, event):
  #--------------------------
    self._events[event.uri] = event
    event.factor = self

  def get_event(self, uri):
  #------------------------
    return self._events[uri]


  def instant(self, when):
  #----------------------
    return self.timeline.instant(when)

  def interval(self, start, duration):
  #-----------------------------------
    return self.timeline.interval(start, duration)


  def map_to_graph(self, rdfmap=None):
  #-----------------------------------
    graph = Graph(self.uri)
    Metadata.map_to_graph(self, graph, rdfmap)
    Metadata.map_to_graph(self.timeline, graph, rdfmap)
    for s in self.signals(): s.map_to_graph(graph, rdfmap)
    for e in self._events.itervalues(): e.map_to_graph(graph, rdfmap)
    return graph


  def metadata_as_string(self, format='turtle', prefixes={ }):
  #-----------------------------------------------------------
    namespaces = { 'bsml': BSML.uri }
    namespaces.update(NAMESPACES)
    namespaces.update(prefixes)
    return self.map_to_graph().serialise(base=str(self.uri) + '/', format=format, prefixes=namespaces)


class Signal(Metadata):
#======================

  metaclass = BSML.Signal

  attributes = ['label', 'units', 'transducer', 'filter', 'rate',  'clock',
                'minFrequency', 'maxFrequency', 'minValue', 'maxValue',
               ]

  def __init__(self, uri, metadata={}):
  #------------------------------------
    super(Signal, self).__init__(uri, metadata=metadata)
    self.recording = None

  ### Are the following really methods on a SignalData class (or RawSignal, cf RawRecording)??
  def read(self, interval):
  #------------------------
    """
    :return: A :class:TimeSeries containing signal data covering the interval.
    """
    raise NotImplementedError, 'Signal.read()'

  def append(self, timeseries):
  #----------------------------
    raise NotImplementedError, 'Signal.append()'

  def data(self, n):
  #----------------
    raise NotImplementedError, 'Signal.data()'

  def time(self, n):
  #----------------
    raise NotImplementedError, 'Signal.time()'

  def __len__(self):
  #----------------
    return 0



class RelativeTimeLine(Metadata):
#================================

  metaclass = TL.RelativeTimeLine

  def __init__(self, uri):
  #----------------------
    super(RelativeTimeLine, self).__init__(uri)

  def instant(self, when):
  #----------------------
    return RelativeInstant(self.makeuri(), when, self)

  def interval(self, start, duration):
  #----------------------------------
    if duration == 0.0: return self.instant(start)
    else:               return RelativeInterval(self.makeuri(), start, duration, self)


class RelativeInstant(Metadata):
#===============================

  metaclass = TL.RelativeInstant

  def __init__(self, uri, when, timeline):
  #---------------------------------------
    super(RelativeInstant, self).__init__(uri)
    self.at = when
    self.timeline = timeline

  def __add__(self, increment):
  #----------------------------
    return RelativeInstant(self.makeuri(True), self.at + increment, self.timeline)


class RelativeInterval(Metadata):
#================================

  metaclass = TL.RelativeInterval

  def __init__(self, uri, start, duration, timeline):
  #--------------------------------------------------
    super(RelativeInterval, self).__init__(uri)
    self.start = start
    self.duration = duration
    self.timeline = timeline

  def __add__(self, increment):
  #----------------------------
    return RelativeInterval(self.makeuri(True), self.start + increment, self.duration, self.timeline)


class Event(Metadata):
#=====================

  metaclass = EVT.Event

  attributes = [ 'description', 'factor', 'time', ]

  def __init__(self, uri, metadata={}):
  #------------------------------------
    ##logging.debug('Event: %s (%s)', uri, repr(uri))
    super(Event, self).__init__(uri, metadata=metadata)

  def map_to_graph(self, graph, rdfmap):
  #-------------------------------------
    Metadata.map_to_graph(self, graph, rdfmap)
    Metadata.map_to_graph(self.time, graph, rdfmap)
