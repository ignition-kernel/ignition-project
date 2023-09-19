import unittest


class AdHocObject(object):
	"""A sloppy JS-like object thing that will work through attributes.
	
	Call _cull_empty to GC unused or empty AHO entries.

	Note that strictness is a massive side effect. If a AHO is introduced into another that's
	set to be strict then the former *becomes* strict. Think of strictness as somewhat viral.
	"""
	__slots__ = [
		'_dict', '_strict', 
		'_clean', '_parent', # a half-hearted attempt at preventing excess garbage collection
	]
	
	
	def __init__(self, initial_source=None, strict=False, parent=None):
		self._strict = strict
		self._parent = parent # backlink!
		self._clean = True
		if isinstance(initial_source, AdHocObject):
			self._dict = initial_source._dict
			if not initial_source._clean:
				if self._strict: # no you're not! fix it!
					self._strict = False
					self._make_strict()
				else:
					self._signal_dirty()
		else:
			self._dict = initial_source or {}
				
	# GET
	def __getitem__(self, key):
		return self._pass_thru_getter(key)

	def __getattr__(self, attr):
		try: # attempt to use the Python attributes _first_ (so our mechanics work!)
			try:
				return super(AdHocObject, self).__getattr__(attr)
			except TypeError as error:
				print(self, attr, type(self))
				raise error
		except AttributeError as error:
			# next try to act like our dictionary
			try:
				return getattr(self._dict, attr)
			except AttributeError:
				pass
			return self._pass_thru_getter(attr)

	def _pass_thru_getter(self, key):
		# pass-thru like it's a getitem
		try:
			# convert dicts to AHO instances 
			if isinstance(self._dict[key], dict):
				self._dict[key] = self._new_chained_attribute(self._dict[key])
			return self._dict[key]
		# if that key doesn't exist yet and we're not acting in a strict way,
		# then return an empty AHO
		except KeyError:
			if self._strict:
				raise KeyError('Strictness faults because key %r not set' % (key,))
			elif key.startswith('_'):
				raise KeyError('Pass thru keys are not allowed to be private or dunders: %r' % (key,))
			else:
				self._dict[key] = self._new_chained_attribute()
				return self._dict[key]

	# SET
	def __setitem__(self, key, value):
		self.__setattr__(key, value)

	def __setattr__(self, attr, value):
		try: # attempt to use the Python attributes _first_ (so our mechanics work!)
			assert attr in self.__slots__
			super(AdHocObject, self).__setattr__(attr, value)
		except (AssertionError, AttributeError) as error:
			self._pass_thru_setter(attr, value)

	def _pass_thru_setter(self, key, value):
		if isinstance(value, dict):
			self._dict[key] = self._new_chained_attribute(value)
		elif isinstance(value, AdHocObject):
			self._add_existing_aho(key, value)
		else:
			self._dict[key] = value

	def _add_existing_aho(self, key, aho_value):
		if self._strict:
			aho_value._make_strict()
		elif not aho_value._clean:
			self._signal_dirty()
		self._dict[key] = aho_value
				
	# DELETE
	def __delattr__(self, attr):
		# this is backward sort as a safety warning: deletion only applies to items
		del self[attr]
	
	def __delitem__(self, key):
		# only delete from the dict
		_ = self._dict.pop(key, None)

	# consistency
	def _new_chained_attribute(self, initial_source=None):
		# check if we've added an empty placeholder
		if not initial_source:
			self._signal_dirty()
		return type(self)(initial_source, strict=self._strict, parent=self)

	@property
	def _parent_key(self):
		"""
		The first key that the parent has that points to this object.

		Yes, it may not be correct, but it'll almost certainly be what almost all sane uses are looking for.
		Remember: AHO is not a dictionary! It's meant to represent an object's attributes. It'd be weird
		to have more than one attribute _literally be another_ as well.
		"""
		if self._parent is not None:
			# unlike normally, this will include blanks, since self might be blank!
			for key, value in self._parent._dict.items():
				if value is self:
					return key
		return None
	
	def _signal_dirty(self):
		# don't resignal
		if self._clean:
			if self._strict:
				self._make_strict()
			else:
				self._clean = False
				if self._parent:
					self._parent._signal_dirty()

	def _make_strict(self):
		if not self._strict:
			# clean up before marking as strict
			self._cull_empty(make_strict=True)
			assert self._strict
	
	def _cull_empty(self, make_strict=False):
		"""In order to make sure any attribute can be interacted with, we return an AHO instance
		for even things not yet set. That means that if it's not used, a thing won't return a value.
		In exchange for that convenience we need to essentially garbage collect those at a later date.

		Note that if set to be strict, this can't happen since empty placeholders can only be set
		when strictness if off. And if we are strict, then empty things should stay anyhow.

		NOTE: Assume that within a chain the strictness is consistent throughout the heirarchy chain.
		"""
		# don't need to clean up if we can't add placeholders
		if self._strict:
			return
		d = self._dict
		for attr in frozenset(d):
			try:
				v = d[attr]
				if isinstance(v, AdHocObject):
					# remove none or empty AdHocObject instances
					# (since AHO likely generated it meaninglessly)
					# (AND an attribute-less dict doesn't mean anything)
					if make_strict:
						v._make_strict()
					else:
						v._cull_empty()
					if not v:
						del d[attr]
			except KeyError:
				pass
		# iterate the full loop before accepting as clean
		else:
			self._clean = True
			# now clean, we can become strict
			if make_strict:
				self._strict = True

	def __eq__(self, other):
		if not self._clean:
			self._cull_empty()
		if isinstance(other, AdHocObject):
			other._cull_empty()
			return self._dict == other._dict
		else:
			return self._dict == other

	def __nonzero__(self):
		if self._strict:
			return bool(self._dict)
		else:
			return bool(self.values())
	__bool__ = __nonzero__
	
	def __len__(self):
		if self._strict:
			return len(self._dict)
		else: # don't count empty attributes
			return len(self.values())

	def __contains__(self, key):
		if self._strict:
			return key in self._dict
		else:
			return key in self._dict and (bool(self[key]) if isinstance(self[key], AdHocObject) else True)

	def __call__(self, *args, **kwargs):
		parent_key = self._parent_key
		if parent_key:
			raise NotImplementedError("AdHocObjects do not have ad hoc methods, so %r is not callable." % (parent_key,))
		raise NotImplementedError("An AdHocObject is a data structure and is not callable.")
		
	def update(self, source):
		"""Acts like a dict update: values in source keys replace self's."""
		if isinstance(source, AdHocObject):
			source = source._dict
		self._dict.update(source)

	def merge(self, source):
		"""
		Recurse through the dict-like keys of source and take their values.
		"""
		for key, value in source.items():
			if not key in self:
				self[key] = value
			# recurse, if self's value is dict-like and mergable
			elif isinstance(value, (dict, AdHocObject)) and isinstance(self[key], AdHocObject):
				self[key].merge(value)
			else:
				self[key] = value

	def __iadd__(self, source):
		self.merge(source)
		return self

	def merge_left(self, source):
		"""Recurse through the dict-like keys of source"""
		for key, value in source.items():
			if not key in self:
				self[key] = value
			# recurse, if self's value is dict-like and mergable
			elif isinstance(value, (dict, AdHocObject)) and isinstance(self[key], AdHocObject):
				self[key].merge_left(value)

	def setdefault(self, key, default=None):
		"""Get an attribute value, if it's not already set then make it default and return that."""
		if key in self:
			# don't return empty aho
			if isinstance(self[key], AdHocObject):
				if bool(self[key]):
					return self[key]
			else:
				return self[key]
		self[key] = default
		return default
	
	def remove(self, source):
		"""The opposite of merge, this will recursively remove LEAF keys that are the same."""
		# is this a single key?
		if isinstance(source, (list, set, tuple)):
			for key in source:
				del self[key] # if key is already missing, AHO silently just says "ok, it's what you meant now"
		elif isinstance(source, (str, unicode)):
			del self[source]
		# remove this leaf node
		elif isinstance(source, AdHocObject) and not source:
			chain = []
			cursor = source
			while cursor._parent is not None:
				parent_key = cursor._parent_key
				assert parent_key
				chain.append(parent_key)
				cursor = cursor._parent
			if chain:
				cursor = self
				for key in reversed(chain[1:]):
					if not key in cursor:
						break
					cursor = cursor[key]
				else:
					del cursor[chain[0]]            
		else:                    
			for key, value in source.items():
				if key in self:
					# recurse, if self's value is dict-like
					if isinstance(value, (dict, AdHocObject)) and isinstance(self[key], AdHocObject):
						self[key].remove(value)
					else:
						del self[key]
					
	def __isub__(self, source):
		self.remove(source)
		return self
					

	def pop(self, key, default=None):
		raise NotImplementedError('AdHocObject is only dict-like - object attributes do not "pop"')
	
	def get(self, key, default=None):
		if key in self:
			# don't return empty aho
			if isinstance(self[key], AdHocObject):
				if bool(self[key]):
					return self[key]
			else:
				return self[key]
		return default
	
	def keys(self):
		if self._strict:
			return self._dict.keys()
		else:
			return [
				k for k,v in self._dict.items()
				# don't return placeholders
				if (v if isinstance(v, AdHocObject) else True)     
			]
	
	def values(self):
		if self._strict:
			return self._dict.values()
		else:
			return [
				v for v in self._dict.values()
				# don't return placeholders
				if (v if isinstance(v, AdHocObject) else True)
			]

	def items(self):
		if self._strict:
			return self._dict.items()
		else:
			return [
				(k,v) for k,v in self._dict.items()
				# don't return placeholders
				if (v if isinstance(v, AdHocObject) else True)     
			]
	
	def _asdict(self):
		self._cull_empty()
		return dict((key, value._asdict() if isinstance(value, AdHocObject) else value)
			for key, value in self._dict.items())
	
	def __repr__(self):
		return repr(self._dict)




class TestingAdHocObject(unittest.TestCase):

	def test_default(self):
		aho = AdHocObject()
		self.assertTrue(aho._clean)
		aho.a = 5
		self.assertTrue(aho._clean)
		aho.b = 111
		self.assertTrue(aho._clean)
		aho.c.qwer = 'qwer'
		self.assertFalse(aho._clean)
		self.assertEqual(aho._asdict(), {'a': 5, 'b': 111, 'c': {'qwer': 'qwer'}})
		self.assertTrue(aho._clean)

	def test_strict(self):
		aho = AdHocObject(strict=True)
		aho.a = 5
		self.assertTrue(aho._clean)
		with self.assertRaises(KeyError):
			aho.c.qwer = 'qwer'

	def test_coerced_strictness(self):
		aho1 = AdHocObject(strict=True)
		aho2 = AdHocObject()
		aho2.a = 55
		self.assertTrue(aho2._clean)
		aho2.c.cc = 'asdf'
		self.assertFalse(aho2._clean)
		self.assertEqual(repr(aho2.d.d), '{}')
		self.assertFalse(aho2._strict)

		# place 2 under 1, which will make 2 strict
		aho1.q = aho2
		self.assertTrue(aho2._strict)
		self.assertTrue(aho2._clean)
		self.assertTrue(aho1._strict)
		self.assertTrue(aho1._clean)
		self.assertEqual(aho2._asdict(),       {'a': 55, 'c': {'cc': 'asdf'}})
		self.assertEqual(aho1._asdict(), {'q': {'a': 55, 'c': {'cc': 'asdf'}}})

		with self.assertRaises(KeyError):
			aho1.c.cc = 'qwer'
			aho2.f
		# these are still linked because that's how dicts work
		# assigned an object! so it naturally shows up there
		aho1.q.c.cc = 'qwer'
		self.assertEqual(aho2.c.cc, 'qwer')


	@property
	def example_dicts(self):
		d1 = {
			'a': 'asdf',
			'b': 'qwer',
			'c': {
				'c1': 1,
				'c2': 22,
				'c3': 333,
			},
			'0': {},
			'1': {'q': 'q'},
		}
		
		d2 = {
			'b': 'QWER',
			'c': {
				'c2': 2222222222222,
				'c4': 'boom',
			},
			'1': 'replaced',
		}
		return d1, d2
	
	def test_merge(self):
		d1, d2 = self.example_dicts
		aho1 = AdHocObject(d1)
		aho2 = AdHocObject(d2)

		aho1.merge(aho2)
		self.assertEqual(
			aho1._asdict(), 
			{'a': 'asdf', 'b': 'QWER', 'c': {
				'c1': 1, 'c2': 2222222222222L, 'c3': 333, 'c4': 'boom'
			}, '0': {}, '1': 'replaced'}
		)
		self.assertEqual(aho1.b, aho2.b)
		self.assertEqual(aho1.c.c2, aho2.c.c2)
		self.assertEqual(aho1.c.c4, aho2.c.c4)
		self.assertEqual(aho1['1'], aho2['1'])
	
	def test_merge_left(self):
		d1, d2 = self.example_dicts
		aho1 = AdHocObject(d1)
		aho2 = AdHocObject(d2)

		aho1.merge_left(aho2)
		self.assertEqual(
			aho1._asdict(), 
			{'a': 'asdf', 'b': 'qwer', 'c': {
				'c1': 1, 'c2': 22, 'c3': 333, 'c4': 'boom'
			}, '0': {}, '1': {'q': 'q'}}
		)
		self.assertNotEqual(aho1.b, aho2.b)
		self.assertNotEqual(aho1.c.c2, aho2.c.c2)
		self.assertEqual(aho1.c.c4, aho2.c.c4)
		self.assertNotEqual(aho1['1'], aho2['1'])

	def test_remove(self):
		d1, d2 = self.example_dicts
		aho1 = AdHocObject(d1)
		aho2 = AdHocObject(d2)

		aho1.remove(aho2)
		self.assertEqual(
			aho1._asdict(), 
			{'a': 'asdf', 'c': {
				'c1': 1, 'c3': 333
			}, '0': {}}
		)

	def test_remove_adhoc_chain(self):
		d1, _ = self.example_dicts
		aho1 = AdHocObject(d1)
		aho1 -= 'a'
		aho1 -= AdHocObject().b
		aho1 -= AdHocObject().c.c2
		self.assertEqual(
			aho1._asdict(),
			{'c': {
				'c1': 1, 'c3': 333
			}, '0': {}, '1': {'q': 'q'}}
		)
		
	
	def test_failures(self):
		aho = AdHocObject()

		with self.assertRaises(NotImplementedError):
			aho.some_thing()

	def test_get(self):
		aho = AdHocObject()
		self.assertEqual(aho.get('a'), None)
		aho.a = 5
		self.assertEqual(aho.get('a'), 5)
		self.assertEqual(aho.get('b'), None)
		self.assertEqual(aho.get('b', 'ASDF'), 'ASDF')
		aho.b = 'QWER'
		self.assertEqual(aho.get('b', 'ASDF'), 'QWER')

	
	def test_setdefault(self):
		aho = AdHocObject()
		self.assertEqual(aho.setdefault('a', 4), 4)
		self.assertEqual(aho.setdefault('a', 9999), 4)
		aho.c
		self.assertEqual(aho.setdefault('c', 'ASDF'), 'ASDF')
		self.assertEqual(aho.setdefault('c', 'QWER'), 'ASDF')