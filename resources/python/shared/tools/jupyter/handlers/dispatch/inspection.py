"""
	Code completion
	
	https://jupyter-protocol.readthedocs.io/en/latest/messaging.html#completion

	This is super _ultra_ fast and dirty.
	Better introspection will be available as features get fleshed out.
	Or I need them. But for now at least something vaguely useful happens
	when tab is hit.

	See .exeuction.coding for more on the wacky hack that grabs contextual info.
"""

logger = shared.tools.jupyter.logging.Logger()

from shared.tools.jupyter.logging import log_message_event

from shared.tools.pretty import pdir

from shared.tools.jupyter.execution.coding import get_object_from_cursor, get_identifier_at_cursor


@log_message_event
def inspect_request(kernel, message):
	"""Object reference info"""
	code_text = message.content.code
	cursor_pos = message.content.cursor_pos
	
	detail_level = message.content.detail_level
	
	obj_data = {}
	obj_metadata = {}
	
	execution_context = kernel.session
	
	obj = None
	try:
		obj, identifier_remainder = get_object_from_cursor(
				code_text, cursor_pos,
				execution_context.python_state_globals,
				execution_context.python_state_locals,
				prefer_calling_context=True,
			)
		obj_data['text/plain'] = pdir(obj, directPrint=False)
		
	except (NameError, AttributeError) as error:
		pass # not found
	
	with kernel.shell_message('inspect_reply', message) as reply:
		if obj:
			reply.content = {
				'status': 'ok',
				
				'found': True,
				'data': obj_data,
				'metadata': obj_metadata,		
			}
		else:
			failed_identifier = get_identifier_at_cursor(code_text, cursor_pos)
			logger.trace('Object not found: %(failed_identifier)r')
			reply.content = {
				'status': 'ok',
				
				'found': False,
				'data': {},
				'metadata': {},		
			}


INSPECTION_DISPATCH = {
	'inspect_request': inspect_request,
}


## found in jupyter_client.adapter in `inspect_reply`
#        if found:
#            lines = []
#            for key in ("call_def", "init_definition", "definition"):
#                if content.get(key, False):
#                    lines.append(content[key])
#                    break
#            for key in ("call_docstring", "init_docstring", "docstring"):
#                if content.get(key, False):
#                    lines.append(content[key])
#                    break
#            if not lines:
#                lines.append("<empty docstring>")
#            data["text/plain"] = "\n".join(lines)

