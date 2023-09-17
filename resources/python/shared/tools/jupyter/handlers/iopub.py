"""
	IOPub

	Jupyter data updates.

	We'll rarely consume off the IOPub bus since, well, we're generating the data.
"""
logger = shared.tools.jupyter.logging.Logger()



def message_handler(kernel, message):
	logger.trace('[Dispatch] [%s]' % (message.header.msg_type,))