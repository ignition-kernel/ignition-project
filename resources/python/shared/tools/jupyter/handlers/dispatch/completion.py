"""
	Object inspection
	
	https://jupyter-protocol.readthedocs.io/en/latest/messaging.html#completion

	This complements the .inspection handler, but instead of object introspection
	this looks for how to finish a partially written word. Same tab-press, different
	context.
"""

logger = shared.tools.jupyter.logging.Logger()

from shared.tools.jupyter.logging import log_message_event
from shared.tools.jupyter.execution.coding import get_identifier_at_cursor, match_references, get_object_from_identifier


@log_message_event
def complete_request(kernel, message):
	"""A simple and naive code completer"""
	code_text = message.content.code
	cursor_pos = message.content.cursor_pos
	
	execution_context = kernel.session
	
	replacement_start = cursor_pos
	
	# TODO: AST the code and combine with what we find in kernel.session tokens
	
	object_identifier = get_identifier_at_cursor(code_text, cursor_pos, perfer_key_context=True)
	
	name_references = match_references(
		object_identifier,
		execution_context.python_state_globals,
		execution_context.python_state_locals,
		return_keys_if_dict=True,
	)
	
	replacement_start = cursor_pos - len(object_identifier)
	if replacement_start < 0: # pure sanity check...
		replacement_start = 0
	
	references_metadata = {}
#	for identifier in name_references:
#		ref = get_object_from_identifier(identifier, 
#			execution_context.python_state_globals,
#			execution_context.python_state_locals,
#			)
#		references_metadata[identifier] = {
#			'label': 'ASDF',
#		}
	
	with kernel.shell_message('complete_reply', message) as reply:
		reply.content = {
			# The list of all matches to the completion request, such as
			# ['a.isalnum', 'a.isalpha'] for the example 'foo = a.isal'
			'matches': name_references,
			
			# The range of text that should be replaced by the above matches when a completion is accepted.
			# typically cursor_end is the same as cursor_pos in the request.
			'cursor_start': replacement_start,
			'cursor_end': cursor_pos,
			
			# Information that frontend plugins might use for extra display information about completions.
			'metadata': references_metadata,
			
			# status should be 'ok' unless an exception was raised during the request,
			# in which case it should be 'error', along with the usual error message content
			# in other messages.
			'status' : 'ok'		
		}
	



COMPLETION_DISPATCH = {
	'complete_request': complete_request,
}