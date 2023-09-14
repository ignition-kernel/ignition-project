from shared.tools.meta import PythonFunctionArguments



class ReorderedInitArgs(type):
	"""
	If not __init__ is set, then use another method for consuming arguments.
	
	This lets another method effectively set the calling signature of a class.
	Helpful if you don't want a user to override __init__ needlessly
	while still having required arguments in the effective replacement.
	"""
	_INIT_ARG_BASE_METHOD_NAME = None
	_INIT_ARG_BASE_CLASS = None
	
	def __new__(metacls, class_name, class_bases, class_configuration):
		assert metacls._INIT_ARG_BASE_METHOD_NAME, 'Metaclasses based on ReorderedInitArgs must set a method that reorders init.'
		
		set_init = False
		
		if all((
			# assume that if an __init__ is provided, they took responsibility
			not '__init__' in class_configuration, 
			# don't reorder if this subclass doesn't define the target method
			metacls._INIT_ARG_BASE_METHOD_NAME in class_configuration,
			# only reorder if we're past the base class and the new class implements the reordering method
			metacls._INIT_ARG_BASE_CLASS and any(
				bc.__name__ == metacls._INIT_ARG_BASE_CLASS 
				for bc in set(mro_bc for bc in class_bases for mro_bc in bc.__mro__)
				)
			)):
			
			method = class_configuration[metacls._INIT_ARG_BASE_METHOD_NAME]
			pfa = PythonFunctionArguments(method)
			
			# first will be self, so skip that
			method_non_default = pfa.nondefault[1:]
			method_args = pfa.args[1:]
			defaults = pfa.defaults
			
			# reorder args into kwargs to make sure the target method gets first pick of args
			def reorder_arguments(args, kwargs):
				if len(args) < len(method_non_default):
					if not all(arg in kwargs for arg in method_non_default[len(args):]):
						raise TypeError('Not enough non-default arguments provided in class init for method %r. Needs %r but got %r' % (method.__name__, method_non_default, args))
				
				reordered_kwargs = kwargs.copy()
				calling_kwargs = {}
				
				# hoist args into kwargs
				for val, arg in zip(args, pfa.args[1:]):
					if arg in kwargs:
						raise TypeError('%r got multiple values for keyword argument %r' % (method, arg,))
					calling_kwargs[arg] = val
				
				# no overlap
				reordered_kwargs.update(calling_kwargs)
				
				# and make sure the remainder get passed along in the same order
				remaining_args = args[min(len(args), len(pfa.args)-1):]
				
				return remaining_args, reordered_kwargs

			set_init = True
			
		new_class = super(ReorderedInitArgs, metacls).__new__(metacls, class_name, class_bases, class_configuration)

		if set_init:
			# must be done after creation so that the super functions
			def __init__(self, *args, **kwargs):
				
				# strictly for testing purposes
				if getattr(self, '_init_args', None) is None:
					self._init_args = (args, kwargs)
				
				rargs, rkwargs = reorder_arguments(args, kwargs)
				super(new_class, self).__init__(*rargs, **rkwargs)
			
			__init__.__name__ = '__init__reordered__'
			
			setattr(new_class, '__init__', __init__)
		
		return new_class


def _run_tests():
	
	# test rigging checker
	def gather_expected_arg_order(instance):
		"""Walk the MRO to find what Python thinks the argument order should be"""
		arg_order = []
		for bc in type(instance).__mro__:
			try:
				init_method = bc.__init__
				if init_method.__name__ == '__init__reordered__':
					init_method = getattr(bc, type(instance)._INIT_ARG_BASE_METHOD_NAME)
				
				for arg in PythonFunctionArguments(init_method).args[1:]:
					if not arg in arg_order:
						arg_order.append(arg)
				
			except AttributeError as error:
				assert 'method_descriptor' in error.message
		
		return arg_order
	
	def results_reflected(instance):
		init_arg_order = gather_expected_arg_order(instance)
		assert len(instance.__dict__) == len(init_arg_order) + 1, (
			'Unexpected number of values (%d): %r' % (len(init_arg_order), instance.__dict__,))
		
		init_args, init_kwargs = instance._init_args
		
		for key, value in instance.__dict__.items():
			if key == '_init_args':
				continue
			assert key==value.lower(), 'failed reflections on %s: %r' % (key, value,)
		
		# obviously set args will be upper case
		set_args = set()
		for arg, value in zip(init_arg_order, init_args):
			assert getattr(instance, arg) == arg.upper() == value, '%r = %r = %r' % (getattr(instance, arg), arg.upper(), value)
			set_args.add(arg)
		
		# and any initial kwarg overrides will also be lower
		for arg in init_kwargs:
			assert getattr(instance, arg) == arg.upper()
			set_args.add(arg)
		
		for arg in (set(init_arg_order) - set_args):
			assert getattr(instance, arg) == arg.lower()
		
		return True
	
	
	print 'Setting up test classes...'
	
	class Base(object):
		def __init__(self, *args, **kwargs):
			#print '[%10s]  %-50r' % ('Base', (args, kwargs,))
			self.init(*args, **kwargs)
	
		def init(self, *args, **kwargs):
			raise NotImplementedError
	
	
	class A1(Base):
		def __init__(self, a1='a1', aa1='aa1', *args, **kwargs):
			#print '[%10s]  %-50r %-50r' % ('A1', (a1, aa1), (args, kwargs,))
			self.a1 = a1
			self.aa1 = aa1
			super(A1, self).__init__(*args, **kwargs)
	
	class A2(A1):
		def __init__(self, a2='a2', *args, **kwargs):
			#print '[%10s]  %-50r %-50r' % ('A2', (a2,), (args, kwargs,))
			self.a2 = a2
			super(A2, self).__init__(*args, **kwargs)
	
	
	class MetaA(ReorderedInitArgs, type):
		
		_INIT_ARG_BASE_METHOD_NAME = 'init'
		_INIT_ARG_BASE_CLASS = 'CoreA'
		
	
	
	class CoreA(A2, A1):
		__metaclass__ = MetaA
		
		def init(self, *args, **kwargs):
			raise NotImplementedError
	
	
	print 'One class, two args'
	
	class MyB(CoreA):
		
		def init(self, b, b2='b2'):
			self.b = b
			self.b2 = b2
			#print '[%10s]  %-50r' % ('B', (b, b2,))
	
	
	
	
	# verify that each calling convention works as expected
	print 'testing...'
	
	
	my_b = MyB('B', 'B2', 'A2', 'A1', 'AA1')
	assert results_reflected(my_b)
	
	
	my_b = MyB('B', 'B2', 'A2', 'A1')
	assert results_reflected(my_b)
	
	my_b = MyB('B', 'B2', 'A2')
	assert results_reflected(my_b)
	
	my_b = MyB('B', 'B2',)
	assert results_reflected(my_b)
	
	my_b = MyB('B',)
	assert results_reflected(my_b)
	
	
	# not enough args
	try:
		my_b = MyB()
	except TypeError:
		pass # expected
	
	
	my_b = MyB('B', b2='B2', a2='A2', a1='A1', aa1='AA1')
	assert results_reflected(my_b)
	
	my_b = MyB('B', a2='A2', b2='B2', aa1='AA1')
	assert results_reflected(my_b)
	
	my_b = MyB(b='B',)
	assert results_reflected(my_b)
	
	
	# duplicate args
	try:
		my_b = MyB('B', 'A2', 'A1', 'AA1', b2='B2')
	except TypeError:
		pass # expected
	
	try:
		my_b = MyB('B', 'B2', 'A1', 'AA1', a2='a2')
	except TypeError:
		pass # expected
	
	
	
	print 'Two classes, each with one, with inheritance'
	
	class MyB2(CoreA):
		
		def init(self, b2):
			self.b2 = b2
			#print '[%10s]  %-50r' % ('B', (b, b2,))
	
	
	class MyB(MyB2):
	
		def init(self, b, *args, **kwargs):
			self.b = b
			super(MyB, self).init(*args, **kwargs)
	
	
	# verify that each calling convention works as expected
	print 'testing...'
	
	
	my_b = MyB('B', 'B2', 'A2', 'A1', 'AA1')
	assert results_reflected(my_b)
	
	
	my_b = MyB('B', 'B2', 'A2', 'A1')
	assert results_reflected(my_b)
	
	my_b = MyB('B', 'B2', 'A2')
	assert results_reflected(my_b)
	
	my_b = MyB('B', 'B2',)
	assert results_reflected(my_b)
	
	
	
	# not enough args
	try:
		my_b = MyB('B',)
	except TypeError:
		pass # expected
	
	try:
		my_b = MyB()
	except TypeError:
		pass # expected
	
	
	my_b = MyB('B', b2='B2', a2='A2', a1='A1', aa1='AA1')
	assert results_reflected(my_b)
	
	my_b = MyB('B', a2='A2', b2='B2', aa1='AA1')
	assert results_reflected(my_b)
	
	
	my_b = MyB('B', b2='B2')
	assert results_reflected(my_b)
	
	# duplicate args
	try:
		my_b = MyB('B', 'A2', 'A1', 'AA1', b2='B2')
		assert results_reflected(my_b)
	except TypeError:
		pass # expected
	
	
	try:
		my_b = MyB('B', 'B2', 'A1', 'AA1', a2='a2')
		assert results_reflected(my_b)
	except TypeError:
		pass # expected
	
	
	#_run_tests()

