"""
	Inspect raw code for introspection
	
	The module name is probably bad, but 'inspection' and 'completion' aren't quite right.

	Ed. note: I'll be honest. The code here is a hack. It's all like the very early versions
	of the metatools pretty printer. Which are _still_ kinda hacky, but at least extremely
	well tested and refined to usable. Code here is meant to sorta get the ball rolling.

	More extensive and thorough code introspection will be added at a later date (likely after
	the debugger and magic commands are added in). I'll try to avoid thirdparty backports,
	but given how rich Python introspection tooling is, it might be worth it.
"""
logger = shared.tools.jupyter.logging.Logger()



import re


def get_identifier_at_cursor(code_text, cursor_pos,
		prefer_calling_context=False,
		perfer_key_context=False,
	):
	"""
	Return the chunk of text in the code that the cursor lays upon.
	"""
	# if we're on the entry of a calling context, return that instead
	# is this info request on a function call?
	if prefer_calling_context and re.match(r"""^[^'"]*['"]{0,3}\(""", code_text[cursor_pos:-30:-1]):
		cursor_pos -= (1 + code_text[cursor_pos:-30:-1].index('('))
	
	# is this autocompleting a dict?
	elif perfer_key_context and re.match(r"""^[^'"]*['"]{0,3}\[""", code_text[cursor_pos:-30:-1]):
		cursor_pos -= (1 + code_text[cursor_pos:-30:-1].index('['))
	
	return (
		(	# read left...
			re.findall(r'^((?:\w|[_.])+)', code_text[cursor_pos::-1]) or ['']
		)[0][::-1]
		+ ( # and append the remainder to the right
			re.findall(r'^(\w+|[_]+)', code_text[cursor_pos+1:]) or ['']
		)[0]
	)


def get_object_from_cursor(code_text, cursor_pos, global_scope=None, local_scope=None, 
		prefer_calling_context=False,
		perfer_key_context=False,
	):
	"""
	Return the object under the cursor given the scopes provided, if any.
	"""
	object_identifier = get_identifier_at_cursor(code_text, cursor_pos, prefer_calling_context, perfer_key_context)
	
	return get_object_from_identifier(object_identifier, global_scope, local_scope)


def get_object_from_identifier(object_identifier, global_scope=None, local_scope=None, potentially_incomplete_chain=False):
	"""
	Return the object by the given identifier and scopes.
	
	May be a chained identifier, so it could resolve given an attribute chain.
	"""
	if '.' in object_identifier:
		identifier_root, _, identifier_chain = object_identifier.partition('.')
	else:
		identifier_root = object_identifier
		identifier_chain = ''

	try:
		obj_root = (local_scope or {})[identifier_root]
	except KeyError:
		try:
			obj_root = (global_scope or {})[identifier_root]
		except KeyError:
			raise NameError(identifier_root)
	
	assert obj_root
	
	if identifier_chain:
		chain_parts = identifier_chain.split('.')
		obj_chained = obj_root
		for part in chain_parts[:-1]:
			obj_chained = getattr(obj_chained, part)
			
		try:
			obj_chained = getattr(obj_chained, chain_parts[-1])
			return obj_chained, ''
		except AttributeError as error:
			if potentially_incomplete_chain:
				return obj_chained, chain_parts[-1]
			else:
				raise error
	else:
		return obj_root, ''


def gather_reordered_attributes(thing, 
		include_private=False, 
		include_dunders=True, 
		dunders_last=True,
		private_last=True,
	):
	attributes = []
	dunders = []
	privates = []
	
	try:
		attribute_listing = sorted(dir(thing))
	except Exception as error:
		try:
			logger.warn('Object %(thing)r for attribute request is broken; could not dir() it!')
		except Exception:
			logger.warn('Object for attribute request is broken; could not dir() it!')
		return []
	
	for attribute in attribute_listing:
		if attribute.startswith('__'):
			dunders.append(attribute)
		elif attribute.startswith('_'):
			privates.append(attribute)
		else:
			attributes.append(attribute)
	
	if include_dunders:
		if dunders_last:
			attributes = attributes + dunders
		else:
			attributes = dunders + attributes

	if include_private:
		if private_last:
			attributes = attributes + privates
		else:
			attributes = privates + attributes
	
	return attributes


def match_references(object_identifier, 
		global_scope=None, local_scope=None,
		return_keys_if_dict=False,
	):
	"""
	Return things that might fill out the identifier (if incomplete) given the scopes.
	
	If given a complete identifier, it will provide the next available options
	"""
	try:
		obj_root, unmatched_identifier_remainder = get_object_from_identifier(
									object_identifier, 
									global_scope, local_scope, 
									potentially_incomplete_chain=True)
	except NameError as error: # find closest simple match
		return sorted([
			identifier 
			for identifier 
			in sorted(
				set(global_scope) | set(local_scope)
			)
			if identifier.startswith(object_identifier)
		])
	
	if unmatched_identifier_remainder:
		partial_identifier = unmatched_identifier_remainder
		matched_identifier = object_identifier[:-len(partial_identifier)-1] # skips the final '.' to be added later for clarity
		
		matches = []
		for attribute in gather_reordered_attributes(obj_root):
			# exact match - grab all of the attributes of _that_
			if attribute == partial_identifier:
				for sub_attribute in gather_reordered_attributes(getattr(obj_root, attribute)):
					matches.append(matched_identifier + '.' + attribute + '.' + sub_attribute)
			# partial match - add anything that looks like it
			elif attribute.startswith(partial_identifier):
				matches.append(matched_identifier + '.' + attribute)
		return matches
	else:
		if return_keys_if_dict and isinstance(obj_root, dict):
			return sorted(obj_root)
		else:
			matched_identifier = object_identifier
			if object_identifier.endswith('.'):  # make sure no trialing '.'
				matched_identifier = matched_identifier[:-1]
			return [
				matched_identifier + '.' + attribute
				for attribute
				in gather_reordered_attributes(obj_root)
			]