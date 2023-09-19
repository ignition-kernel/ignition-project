"""
	Utility functions to pack up some odds-n-ends

"""

from shared.tools.thread import findThreads
from shared.tools.thread import async
from time import sleep



#####################
# regex match helpers

import re

def re_match_groupdict(pattern, value, flags=0):
	match = re.match(pattern, value, flags)
	if match:
		return match.groupdict()
	else:
		return {}

def re_match_extract(pattern, value, name):
	return re_match_groupdict(pattern, value).get(name)


######################
# random identifer gen

import random
import string

def random_id(length=4):
	return ''.join(random.choice(string.hexdigits[:16]) for x in range(length))


def apply_jitter(delay, jitter_fraction):
	width = int((delay * jitter_fraction) * 1000)
	offset = random.randint(-width, width) / 1000.0
	return delay + offset


#####################
# thorough error logs

from shared.tools.error import *


####################
# Make lookup easier
#  (avoid getattr)

class DictLikeAccessMixin(object):
	
	def __getitem__(self, item):
		assert not item.startswith('_'), 'Dict access is not for private parts'
		try:
			return getattr(self, item)
		except AttributeError:
			raise KeyError('%r is not accessible from Kernel Context' % (item,))

	def __setitem__(self, item, value):
		assert not item.startswith('_'), 'Dict access is not for private parts'
		try:
			setattr(self, item, value)
		except AttributeError:
			raise KeyError('%r is not accessible from Kernel Context' % (item,))       

	# allows for format and kwarg interpolation
	def __len__(self):
		return len(self.keys())
	
	def __iter__(self):
		return (attr for attr in dir(self) if not attr.startswith('_'))
	
	def keys(self):
		return list(iter(self))

####################
# jailbreaking stack

import sys

from shared.tools.thread import getThreadFrame

class NameNotFoundError(NameError): pass # maybe should be a KeyError?
class ObjectNotFoundError(ValueError): pass
class TypeNotFoundError(ValueError): pass

def type_pedigree_signature(object_type):
	return ', '.join(tuple(
		repr(base_class) for base_class in object_type.__mro__
	))


def get_from_thread(thread, object_type, get_all_instances=False, heuristic_match=True):
	"""
	Get object from the thread, searching from the root frame up.
	
	Returns on the first frame that yields a result, and on the first object it finds in local scope.
	IFF get_all_instances is set, then expect a list, otherwise it'll return the first instance.

	On failure to find anything it throws a NotFoundError.
	"""
	type_name = repr(object_type)
	type_pedigree = type_pedigree_signature(object_type) if heuristic_match else None
	
	instances = []
	frame = getThreadFrame(thread)
	stack = [frame]
	while frame.f_back:
		stack.append(frame.f_back)
		frame = frame.f_back
	try:
		for frame in reversed(stack):
			for value in frame.f_locals.values():
				if isinstance(value, object_type):
					if get_all_instances:
						instances.append(value)
					else:
						return value
				# if classes got recompiled or reloaded - or threads simply started
				# with different initial loadings, then we'll need to loosen our
				# definition of "isinstance" since an object may very well simply
				# be an instance of the same class from a parallel universe
				elif heuristic_match:
					# quick check
					if type_name == repr(type(value)):
						# more thorough pedigree check
						if type_pedigree == type_pedigree_signature(type(value)):
							if get_all_instances:
								instances.append(value)
							else:
								return value
			if instances:
				return instances
		else:
			raise TypeNotFoundError
	except: 
		# frames that continued execution and are now defunct/missing/gc'd can throw errors, too 
		# (but ignore them, since they won't have the object we're looking for)
		raise TypeNotFoundError('Type %r not found in execution stack' % (object_type,))