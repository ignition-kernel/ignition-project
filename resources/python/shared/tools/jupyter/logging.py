"""
	While the kernel has its own logging setup, this provides an out-of-band
	way to get logs. For example, we need loggers for the modules themselves despite
	them not running in the kernel object itself.

	It also pre-tunes all these loggers to the DEFAULT_LOGGING_LEVEL here if they're
	not Kernel loggers.

	Every script module should start with the following:

		logger = shared.tools.jupyter.logging.Logger()
"""

from functools import wraps, partial
from shared.tools.logging import Logger

DEFAULT_LOGGING_LEVEL = 'info'

Logger = partial(Logger, logging_level=DEFAULT_LOGGING_LEVEL)

logger = Logger()



def log_message_event(message_handler):
	module_name = message_handler.func_code.co_filename[1:-1].rpartition('.')[2]
	function_name = message_handler.func_code.co_name

	logger = shared.tools.logging.Logger('Jupyter %s' % (module_name,), logging_level=DEFAULT_LOGGING_LEVEL)
	
	@wraps(message_handler)
	def logged_message_handler(kernel, message):
		
		logger.trace('[%s] message (%s) received for %r' % (
			function_name, message.header.msg_id, kernel))
		
		message_handler(kernel, message)
		
		logger.trace('[%s] message (%s) handled for %r' % (
			function_name, message.header.msg_id, kernel))
	
	return logged_message_handler