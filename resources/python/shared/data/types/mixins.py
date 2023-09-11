"""
	Helper mixins for flavoring classes
"""
from collections import defaultdict

__all__ = [
	'CountInstanceMixin', 
	'ImmutableDictMixin',
	'TemporaryContextMixin',
	]



class CountInstanceMixin(object):
	"""Count how many times an instance was spotted."""
	_instance_counts = defaultdict(int)
	
	def __new__(cls, *args, **kwargs):
		self = super(CountInstanceMixin, cls).__new__(cls, *args, **kwargs)
		cls._instance_counts[self] += 1
		return self



class ImmutableDictMixin(object):
	"""Place this more to the left of the class inheritance to disable setting values. (Like a tuple)"""
	
	def __setitem__(self, key, value):
		raise RuntimeError('Class disallows mutation via dict methods')
		
	def __delitem__(self, key):
		raise RuntimeError('Class disallows mutation via dict methods')



class TemporaryContextMixin(object):
	"""Make instances safe for temporary reference."""
	
	def __enter__(self):
		self.stage()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.release()
	
	def stage(self):
		pass
	
	def release(self):
		pass
