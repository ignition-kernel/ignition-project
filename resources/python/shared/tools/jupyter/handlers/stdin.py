"""
	StdIn

	Jupyter providing a kernel with input.
"""
logger = shared.tools.jupyter.logging.Logger()



def message_handler(kernel, message):
	logger.trace('[Dispatch] [%s]' % (message.header.msg_type,))