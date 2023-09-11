"""


"""
logger = shared.tools.jupyter.logging.Logger()


from shared.tools.jupyter.catch import *
from shared.tools.jupyter.logging import log_message_event
from shared.tools.jupyter.handlers.dispatch.comms import COMMS_DISPATCH
from shared.tools.jupyter.handlers.dispatch.kernel import KERNEL_DISPATCH
from shared.tools.jupyter.handlers.dispatch.execution import EXECUTION_DISPATCH
from shared.tools.jupyter.handlers.dispatch.completion import COMPLETION_DISPATCH
from shared.tools.jupyter.handlers.dispatch.inspection import INSPECTION_DISPATCH


SHELL_DISPATCH = {}

SHELL_DISPATCH.update(KERNEL_DISPATCH)
SHELL_DISPATCH.update(COMMS_DISPATCH)
SHELL_DISPATCH.update(EXECUTION_DISPATCH)
SHELL_DISPATCH.update(COMPLETION_DISPATCH)
SHELL_DISPATCH.update(INSPECTION_DISPATCH)




# TODO: make dispatch reloadable by browsing modules for collections

def live_load_dispatch():
	import shared.tools.jupyter.handlers.dispatch as dispatch_root
	dispatch_root_dict = dispatch_root.getDict()
	
	dispatch_map = {}
	
	for module_name in sorted(dispatch_root_dict):
		try:
			module = dispatch_root_dict[module_name]
			for thing in module.getDict():
				if thing.endswith('_DISPATCH'):
					dispatch_map.update(module[thing])
		except Exception as error:
			logger.debug('Dispatcher failed to load in %(module_name)s: %(error)r')
	
	return dispatch_map



def message_handler(kernel, message):
	
	logger.trace('[Dispatch] [%s]' % (message.header.msg_type,))
	
	(
		live_load_dispatch() if kernel.live_reload else SHELL_DISPATCH
	).get(
		message.header.msg_type, 
		not_implemented_message_type
	)(kernel, message)



def not_implemented_message_type(kernel, message):
	logger.error("Unimplemented message type: %r" % (message.header.msg_type,))



