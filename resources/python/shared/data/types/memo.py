"""
	Memoizing-like helpers
"""
from java.lang.System import currentTimeMillis
from datetime import datetime
import sys

#from weakref import WeakValueDictionary

class CacheOverflow(MemoryError):
	def __init__(self, exc_arg=None, cache=None):
		super(CacheOverflow, self).__init__(exc_arg)
		self.cause = cache



class EnumeratedLookup(object):
	__slots__ = [
		'__initialized__',
		'__lookup_table__', 
		'__lookup_index__',
	
		'_instance_label',
		'_instance_index',
	]
	__module__ = shared.tools.meta.get_module_path(1)
	_instances = {}
	_enumerated_lookups = None
	
	CACHE_SIZE_LIMIT = 250000 # quarter million
	
	def __new__(cls, seed=None, label=None):
		existing = cls._instances.get(label)
		
		if existing is None or (seed and existing.seed != seed):
			
			instance = super(EnumeratedLookup, cls).__new__(cls,)
			
			if cls._enumerated_lookups: # base uninit case check for this core base class
				# keep track of only one of a label at a time
				if existing:
					
					existing_index = cls._enumerated_lookups.index(existing)
					cls._enumerated_lookups.__lookup_table__[existing_index] = None
					del cls._enumerated_lookups.__lookup_index__[existing]
					existing._instance_index = None
				
				instance._instance_index = cls._enumerated_lookups.index(instance)
			
			else:
				instance._instance_index = 0
			
			instance._instance_label = label
			instance.clear(seed)
			
			cls._instances[label or repr(instance)] = instance
			
			return instance
		
		return existing
	
	
	def index(self, value):
		try:
			return self.__lookup_index__[value]
		except KeyError:
			if len(self.__lookup_table__) > self.CACHE_SIZE_LIMIT:
				raise CacheOverflow('Cache "%s" (%s) hit maximum size (%d)' % (self.label, self.timestamp, self.CACHE_SIZE_LIMIT), self)
			self.__lookup_index__[value] = len(self.__lookup_table__)
			self.__lookup_table__.append(value)
			return self.__lookup_index__[value]
	
	def add(self, value):
		_ = self.index(value)
	
	def remove(self, value):
		del self[self.index(value)]
	
	def value(self, index):
		return self.__lookup_table__[index]
	
	def encode(self, *values):
		return tuple(self.index(value) for value in values)
	
	def decode(self, *indexes):
		return tuple(self.value(index) for index in indexes)
	
	def clear(self, seed=None):
		self.__initialized__ = seed or currentTimeMillis()
		self.__lookup_table__ = list()
		self.__lookup_index__ = dict()
	
	@property
	def is_primary(self):
		return EnumeratedLookup._instances.get(self.label) is self
	
	@property
	def seed(self):
		return self.__initialized__

	def __del__(self, index):
		item = self.__lookup_table__[index]
		del self.__lookup_index__[item]
		self.__lookup_table__[index] = None

	@property
	def label(self):
		return self._instance_label
	
	@property
	def timestamp(self):
		return datetime.fromtimestamp(self.__initialized__/1000.0).isoformat(' ')
	
	def __len__(self):
		return len(self.__lookup_table__)
	
	def __getitem__(self, index):
		return self.__lookup_table__[index]

	def __call__(self, *args, **kwargs):
		raise NotImplementedError('Access the enumerated lookup via .index(value) or .value(index)')
	
	def __iter__(self):
		return self.__lookup_table__
	
	def __repr__(self):
		return '<EnumLookup %r [%s] @ %s>' % (
			self._instance_label, self._instance_index or '-', self.timestamp,)

# bootstrap the tracking of the lookups themselves (for recording table dumps)
EnumeratedLookup._enumerated_lookups = EnumeratedLookup(label='EnumeratedLookup')
# ensure falsy indexes are _always_ falsy for this lookup
_ = EnumeratedLookup._enumerated_lookups.encode(None)
# add itself for introspection!
_ = EnumeratedLookup._enumerated_lookups.encode(EnumeratedLookup._enumerated_lookups)
