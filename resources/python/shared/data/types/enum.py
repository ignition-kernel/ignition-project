"""A simple enumeration class.

	This is a bit different in that it's meant to be flexible to use
	by implementing both the class attribute and dict access, and it
	can enumerate across any value. More than that, it behaves with
	equivalency because the enum entries aren't just integers.
	
	>>> from shared.tools.pretty import p,pdir,install;install()
	>>> from shared.data.types.enum import Enum
	>>> class ExampleEnum(Enum):
	... 	Value1 = 1
	... 	Value2 = 2
	... 	ValueA = 'A'
	>>> class AnotherEnum(Enum):
	... 	ASDF = 'asdf'
	... 	qwer = 'QWER'
	>>> class Both(ExampleEnum, AnotherEnum):
	... 	both = 1000
	
	>>> p(dict(Both))
	<'dict'> of 6 elements
	      ASDF : <Both.ASDF asdf>
	    Value1 : <Both.Value1 1> 
	    Value2 : <Both.Value2 2> 
	    ValueA : <Both.ValueA A> 
	      both : <Both.both 1000>
	      qwer : <Both.qwer QWER>
	>>> ExampleEnum(1)
	1
	>>> ExampleEnum.Value1
	1
	>>> ExampleEnum['Value1'] is ExampleEnum.Value1
	True
	>>> ExampleEnum['Value1'] is ExampleEnum.Value1 is 1
	False
	>>> ExampleEnum['Value1'] is Both.Value1
	False
	>>> ExampleEnum['Value1'] == Both.Value1
	True
	>>> 
	>>> AnotherEnum.asdf
	Traceback (most recent call last):
	  File "<input>", line 1, in <module>
	AttributeError: type object 'AnotherEnum' has no attribute 'asdf'
	>>> AnotherEnum.ASDF
	asdf
	
	Note that enums do _not_ instantiate, but always return their enum value:
	
	>>> ExampleEnum('A')
	A
	>>> repr(ExampleEnum('A'))
	<ExampleEnum.ValueA A>
	>>> ExampleEnum.ValueA
	A
	>>> repr(ExampleEnum.ValueA)
	<ExampleEnum.ValueA A>
	>>> ExampleEnum('A') is ExampleEnum.ValueA
	True
"""
		

__copyright__ = """Copyright (C) 2022 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'

__all__ = ['Enum']


class MetaEnumValue(type):
	
	def __init__(cls, clsname, bases, attributes):
		for base in bases:
			if base.__name__ != 'EnumValue':
				setattr(cls, '_type', base)
				break
		
		def __setattr__readonly__(self, key, _):
			raise AttributeError("<%r> is readonly" % self)
		setattr(cls, '__setattr__', __setattr__readonly__)

		
class EnumValue(object):
	_parent = None
	_type = None
		
	# def __str__(self):
	#     return '%s.%s' % (self._parent.__name__, self.__class__.__name__)

	def __repr__(self):
		return '<%s.%s %s>' % (self._parent.__name__, 
							   self.__class__.__name__, 
							   self._type.__str__(self))
	

	
class MetaEnum(type):
	
	_initFields = ('_fields', '_values')
	_class_initialized = False
		
	def __init__(cls, clsname, bases, attributes):
		
		super(MetaEnum, cls).__setattr__('_class_initialized', False) # bypass interlock
		
		# collect any parents, if any, to allow override/extending enums    
		fvs = []
		for base in reversed(bases):
			if type(base) is MetaEnum:
				fvs += [(field,value) for field, value in zip(base._fields, base._values)]

		fvs += [(key,value) for key, value in attributes.items() if not key.startswith('_')]

		if fvs:
			try:
				fields,values = zip(*sorted(fvs, key=lambda key_value: key_value[1]))
			# it's possible values won't be comparable - so use the key in that case
			except TypeError:
				fields,values = zip(*sorted(fvs, key=lambda key_value: key_value[0]))
		
			setattr(cls, '_fields', fields)
			setattr(cls, '_values', values)
			
			for key,value in fvs:
				try:
					EnumAttribute = MetaEnumValue(key, (EnumValue,type(value)), {'_parent': cls})
					setattr(cls, key, EnumAttribute(value))
				except TypeError: # for things like re.Pattern that can't be mixed in
					setattr(cls, key, value)

			
		else:
			setattr(cls, '_fields', tuple())
			setattr(cls, '_values', tuple())
		
		cls._class_initialized = True
				
			
	def __setattr__(cls, key, value):
		if cls._class_initialized:
			raise AttributeError("<%s> attributes are readonly" % cls.__name__)
		else:
			super(MetaEnum, cls).__setattr__(key, value)                
				
	def __contains__(cls, enum_key):
		return (enum_key in cls._fields) or (enum_key in cls._values)
	
	def key(cls, value):
		return cls._fields[cls._values.index(value)]

	def keys(cls):
		return cls._fields

	def value(cls, key):
		return cls._values[cls._fields.index(key)]

	def values(cls):
		return cls._values

	def items(cls):
		return zip(cls._fields, cls._values)

	def __iter__(cls):
		return iter(getattr(cls, field) for field in cls._fields)
	
	def __getitem__(cls, attribute):
		return getattr(cls, attribute)
	
	def __str__(cls):
		return cls.__name__
	
	def __repr__(cls):
		return "<%s {%s}>" % (cls.__name__, 
							  ', '.join("%s: %s" % (repr(field), repr(value)) 
										for field, value in zip(cls._fields, cls._values)))

	
class Enum(object):
	__metaclass__ = MetaEnum
	__slots__ = tuple()
		
	_fields = tuple()
	_values = tuple()
	
	def __new__(cls, value=None):
		if value is not None and value in cls._values:
			return getattr(cls, cls._fields[[i for i,v in enumerate(cls._values) if v == value][0]])

		# allow coersion
		if value is not None and value in cls._fields:
			return getattr(cls, value)
			
		raise KeyError("%s is an enumeration and %r is not a valid value." % (cls.__name__, value)) 
	
	def __init__(cls):
		raise NotImplementedError("%s is an enumeration and does not support instantiation." % cls.__name__)
		
	def __setattr__(cls, key, value):
		raise AttributeError("<%s> attributes are readonly" % cls.__name__)
