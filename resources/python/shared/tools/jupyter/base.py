"""
	Base methods for mixins to ensure methods are available for super cooperation
"""
import itertools



class JupyterKernelBaseMixin(object):
	
	def initialize_kernel(self, **init_kwargs):
		pass
	
	def tear_down(self):
		pass


	# include the prep methods to allow user overrides
	_PREP_METHODS = ('init', 'launch', 'tear_down')
	
	__slots__ = tuple(
		'%s_%s' % (a,b) 
		for a,b 
		in itertools.product(
			('pre', 'post'), 
			_PREP_METHODS)
		)
	
	_SLOT_DEFAULTS = {}

	# default overrides for certain
	for a,b in itertools.product(('pre', 'post'), _PREP_METHODS):
		_SLOT_DEFAULTS['%s_%s' % (a,b)] = lambda kernel: None
	

	# runtime user overrides
	# (unbound, so we grab it, then fire it)
	def _pre_launch(self):
		self.pre_launch(self)
	
	def _post_launch(self):
		self.post_launch(self)
	
	def _pre_init(self):
		self.pre_init(self)
	
	def _post_init(self):
		self.post_init(self)
	
	def _pre_tear_down(self):
		self.pre_tear_down(self)
	
	def _post_tear_down(self):
		self.post_tear_down(self)