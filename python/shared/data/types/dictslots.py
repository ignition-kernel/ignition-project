"""
	Abusing class slots and dict access
	
	It's handy to use __slots__ for classes with known attributes.
	They also use less memory and are faster to instantiate.
	
	DictSlotsMixin adds the dict-like methods to make classes that are
	basically structs accessibly like they're dictionaries.
	


"""


class DictSlotsMixin(object):
	"""Add to a class with __slots__ so that it's elements can be accessed conveniently"""
	
	def __getitem__(self, key):
		try:
			return getattr(self, key)
		except AttributeError:
			raise KeyError('%s is not an attribute of %r' % (key, self))
	
	def __setitem__(self, key, value):
		print key, value
		try:
			setattr(self, key, value)
		except AttributeError:
			raise KeyError('%s is not an attribute of %r' % (key, self))

	def __delitem__(self, key):
		try:
			setattr(self, key, None)
		except AttributeError:
			raise KeyError('%s is not an attribute of %r' % (key, self))

	@classmethod
	def keys(self):
		return self.__slots__
		
	def values(self):
		return tuple(getattr(self, key) for key in self.__slots__)
		
	def items(self):
		return tuple((key, getattr(self, key)) for key in self.__slots__)
		
		
	def asdict(self):
		d = {}
		for key in self.keys():
			value = getattr(self, key)
			if isinstance(value, DictSlotsMixin):
				value = value.asdict()
			elif isinstance(value, (list, tuple, set)):
				value = [
					v.asdict() if isinstance(v, DictSlotsMixin) else v
					for v in value
				]
			d[key] = value
		return d

	@property
	def format_dict(self):
		return self.asdict()
	
	def astuple(self):
		t = tuple()
		for key in self.keys():
			value = getattr(self, key)
			if isinstance(value, DictSlotsMixin):
				value = value.astuple()
			elif isinstance(value, (list, tuple, set)):
				value = tuple(
					v.astuple() if isinstance(v, DictSlotsMixin) else v
					for v in value
				)
			t += (value,)
		return t
		
	def __getstate__(self):
		return tuple(getattr(self, key) for key in self.keys())
	
	def __setstate__(self, new_state):
		for key, value in zip(self.keys(), new_state):
			setattr(self, key, value)
	
	@property
	def format_tuple(self):
		return self.astuple()


	def __len__(self):
		return len(self.__slots__)

	def __iter__(self):
		for key in self.__slots__:
			yield key
			
	def __reversed__(self):
		for key in reversed(self.__slots__):
			yield key

