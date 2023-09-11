"""
	Plain Old Java Objects
	
	Helpers for dealing with and wrapping Java objects!

"""
from java.lang import Object as JavaObject

import re

from shared.data.types.memo import EnumeratedLookup


__all__ = [
	'PassThruJavaWrapper',
	'EnumeratedPassThruJavaWrapper',
]


def make_accessor(some_attribute, prefix='get'):
	assert some_attribute
	
	# if already looks like a getter, use that
	if re.match(prefix + '[A-Z].*', some_attribute):
		return some_attribute
	
	parts = re.split('\W', re.sub('[_ -]', ' ', some_attribute))
	
	if parts[0] == prefix:
		parts = parts[1:]
		
	return prefix + ''.join(part.capitalize() for part in parts)



def fill_out_dict(source, keys, separator='.'):
	d = {}
	for key in keys:
		sd = d
		# resolve nesting
		attr_chain = key.split(separator)
		for subd in attr_chain[:-1]:
			if subd not in sd:
				sd[subd] = {}
			sd = sd[subd]
		try:
			sd[attr_chain[-1]] = source[key]
		except TypeError as error:
			if 'object does not support item assignment' in error.message:
				raise TypeError(error.message + '\nCheck that a called out key specified is not both directly named '
								' _and_ has nested attributes called out (like both instant AND instant.nano)')
			else:
				raise error
	return d



class PassThruJavaWrapper(object):
	"""A super charged wrapper for Java objects. 
	
	It'll generally act just like the plain old Java object, but puts more effort into
	simplifying / resolving the accessors (builtin Jython just does `get`).
	Any attribute can be accessed like it's a dict, as well.
	
	Moreover, these keys can also be chained or compound. Anything that returns a JavaObject
	will also be wrapped as a PassThruJavaWrapper
	"""
	__slots__ = ['_object']
	
	_RESOLVED_ACCESSOR_CHAINS = {}
	
	def __init__(self, pojo):
		self._object = pojo
	
	def __getattr__(self, attr):
		try: # attempt to use the Python attributes _first_ (so our mechanics work!)
			return super(PassThruJavaWrapper, self).__getattr__(attr)
		except AttributeError as error:
			target = self._resolve(attr)
			if isinstance(target, JavaObject):
				return PassThruJavaWrapper(target)
			else:
				return target
			raise error
	
	def __getitem__(self, key):
		return self._resolve(key)
	
	
	def _resolve(self, key):
		target = self._object
		
		accessor_chain = self._RESOLVED_ACCESSOR_CHAINS.get((type(target), key), [])
		
		# memoize caching the resolved chain
		# (once warmed up, should be fairly fast)
		if accessor_chain:
			for accessor, called in accessor_chain:
				target = getattr(target, accessor)
				if called:
					target = target()
		else: # create the attribute chain needed
			try:
				for attribute in key.split('.'):
					if isinstance(target, JavaObject):
						for java_prefix in ('get', 'to', 'as'):
							accessor = make_accessor(attribute, java_prefix)
							try:
								target = getattr(target, accessor)()
								accessor_chain.append((accessor, True))
								break
							except AttributeError:
								continue
						else:
							target = getattr(target, attribute)
							accessor_chain.append((attribute, False))
					else:
						target = getattr(target, attribute)
						accessor_chain.append((attribute, False))
			except AttributeError as error:
				target = getattr(target, key)
				accessor_chain.append((key, False))
			
			# cache the resulting found chain
			self._RESOLVED_ACCESSOR_CHAINS[(type(target), key)] = tuple(accessor_chain)
			
		if callable(target) and not isinstance(target, type):
			target = target()
		
		# 1.234E-17 is a stupid number
		if isinstance(target, float):
			return round(target, 6)
		return target

	
	def __str__(self):
		return str(self._object)
	
	def __repr__(self):
		return repr(self._object)




class MetaEnumeratedPassThruJavaWrapper(type):
	"""Enable a pass thru wrapper that 
	
	"""
	__pojo_types__ = EnumeratedLookup(label='POJO PassThru Type Enumeration')
	
	def __new__(metacls, class_name, class_bases, class_configuration):
		class_configuration['__attribute_paths__'] = None
		class_configuration['_REFACTOR_REVERSE_LOOKUP'] = None
		new_class = super(MetaEnumeratedPassThruJavaWrapper, metacls).__new__(metacls, class_name, class_bases, class_configuration)
		# log the type so that the bincoder can alias
		metacls.__pojo_types__.add(new_class.__classpath__)
		# add the attribute/key paths for easier lookup
		new_class.__attribute_paths__ = tuple(
				new_class._REFACTOR.get(attr, attr) 
				for attr in new_class._ATTRIBUTES
			)
		new_class._REFACTOR_REVERSE_LOOKUP = {v:k for k,v in new_class._REFACTOR.items()}
		return new_class
		
#	def __init__(new_class, class_name, class_bases, class_configuration):
#		super(MetaEnumeratedPassThruMixin, new_class).__init__
#		metacls.__pojo_types__.add(new_class.__classpath__)

	@property
	def __classpath__(cls):
		return cls.__module__ + '.' + cls.__name__



class EnumeratedPassThruJavaWrapper(PassThruJavaWrapper):
	__metaclass__ = MetaEnumeratedPassThruJavaWrapper

	# pre-declare attributes of interest
	_ATTRIBUTES = []
	_REFACTOR = {}
	_REFACTOR_REVERSE_LOOKUP = None

	def __dump__(self):
		return (type(self).__pojo_types__.index(type(self).__classpath__),) + self.__getstate__()
	
	def __load__(self, state):
		eptjw_type = type(self).__pojo_types__.value(state[0])
		return PojoEptwShim[type(self)](state[1:])


	def _resolve(self, key):
		key = self._REFACTOR_REVERSE_LOOKUP.get(key,key)
		return super(EnumeratedPassThruJavaWrapper,self)._resolve(key)


	def __getstate__(self):
		return tuple(self[key] for key in self._ATTRIBUTES)
	
	def asdict(self):
		return fill_out_dict(self, self.__attribute_paths__)




class MetaPojoEptwShim(type):
	__pojo_eptw_map__ = {}
	__SHIM_CLASS__ = None


	def __new__(metacls, class_name, class_bases, class_configuration):
		if metacls.__SHIM_CLASS__ is None:
			new_class = super(MetaPojoEptwShim, metacls).__new__(metacls, class_name, class_bases, class_configuration)
			metacls.__SHIM_CLASS__ = new_class
			return new_class
		
		# grab the type for lookup
		if not class_bases:
			pojo_ptw_type = class_configuration['__base_class__']
		elif len(class_bases):
			pojo_ptw_type = class_bases[0]
			assert pojo_ptw_type is not metacls.__SHIM_CLASS__, 'Subclasses of PojoShim must point to the class they are shimming'
		elif len(class_bases) == 2:
			# grab who we're shimming (hint: it's the not-shim one)
			pojo_ptw_type = class_bases[class_bases[0] is metacls.__SHIM_CLASS__]
		else:
			raise TypeError('Can not shim more than one class at once; too many bases: %r' % (class_bases,))
		
		try:
			return metacls.__pojo_eptw_map__[pojo_ptw_type]
		except KeyError:
			# prime for faster lookup and chaining attributes
			reverse_lookup = {}
			for ix, attr_path in enumerate(pojo_ptw_type.__attribute_paths__):
				reverse_lookup[attr_path] = ix
				chains = attr_path.count('.')
				if chains:
					parts = attr_path.split('.')
					for chain_ix in range(chains):
						reverse_lookup['.'.join(parts[:chain_ix+1])] = NotImplemented
				
				# for full backward compatibility, allow for shims to cover the non-aliased corrections
				alias = pojo_ptw_type._REFACTOR_REVERSE_LOOKUP.get(attr_path, None)
				if not alias:
					continue
				reverse_lookup[alias] = ix
				chains = alias.count('.')
				if chains:
					parts = alias.split('.')
					for chain_ix in range(chains):
						reverse_lookup['.'.join(parts[:chain_ix+1])] = NotImplemented
				
			new_class = super(MetaPojoEptwShim, metacls).__new__(metacls, class_name, 
				(metacls.__SHIM_CLASS__,), 
				{
					'__base_class__': pojo_ptw_type,
					'__attribute_reverse_lookup__': reverse_lookup,
				},
			)
			metacls.__pojo_eptw_map__[pojo_ptw_type] = new_class
			return new_class
	
	def __getitem__(cls, base_type):
		try:
			return MetaPojoEptwShim.__pojo_eptw_map__[base_type]
		except KeyError:
			return MetaPojoEptwShim(base_type.__name__ + 'Shim', tuple(), {'__base_class__': base_type})



class PojoEptwShim(object):
	__metaclass__ = MetaPojoEptwShim
	__base_class__ = PassThruJavaWrapper
	
	__slots__ = ['__state__', '_attribute_chain']
	
	def __init__(self, state, in_progress_chain=None):
		self.__state__ = tuple(state)
		self._in_progress_chain = in_progress_chain

	
	def __getattr__(self, attr):
		try: # attempt to use the Python attributes _first_ (so our mechanics work!)
			return super(PojoEptwShim, self).__getattr__(attr)
		except AttributeError as error:
			try:
				lookup_key = self._in_progress_chain + '.' + attr if self._in_progress_chain else attr
				v = self.__attribute_reverse_lookup__[lookup_key]
				if v is NotImplemented:
					return type(self)(self.__state__, lookup_key)
				else:
					return self.__state__[v]
			except KeyError:
				if "'super' object has no attribute '__getattr__'" in error.message:
					raise AttributeError('Attribute did not resolve (be sure to use aliased naming): %s' % (
										  attr if not self._in_progress_chain else lookup_key,))
				else:
					raise error
	
	
	def __getitem__(self, key):
		return self.__state__[self.__attribute_reverse_lookup__[key]]


	def asdict(self):
		return fill_out_dict(self, self.__base_class__.__attribute_paths__)




def _run_tests():
	
	from java.util import Date
	
	
	class EptwDate(EnumeratedPassThruJavaWrapper):
		_ATTRIBUTES = [
			attr.strip() for attr in
			"""date year month day hours minutes seconds	
			""".split()
		] + ['timezone offset', 'instant.nano']
		
		_REFACTOR = {
			'instant.nano': 'instant.nanoseconds'
		}
		
		def __str__(self):
			return '%(hours)02d:%(minutes)02d:%(seconds)02d' % self
	
	
	now = Date()
	
	ptw_test = PassThruJavaWrapper(now)
	
	assert re.match(r'\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d.\d\d\dZ ==> \d\d',
		'%(instant)r ==> %(hours)02d' % ptw_test)
	
	test = EptwDate(now)
	
	assert re.match('[0-9][0-9]:[0-9][0-9]:[0-9][0-9]', str(test))
	assert test.asdict()

	test_shim = PojoEptwShim[EptwDate](test.__getstate__())
		
	assert isinstance(test_shim.year, int)
	assert isinstance(test_shim.instant, PojoEptwShim)
	assert isinstance(test_shim.instant.nanoseconds, (int, long))
	
	assert test_shim.asdict() == test.asdict()










