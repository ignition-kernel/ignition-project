"""


"""
logger = shared.tools.jupyter.logging.Logger()

from datetime import datetime



def payload_handler(kernel, bytes_payload):
	logger.trace('Ping recieved << %r' % (bytes_payload,))
	if kernel.session:
		kernel.heartbeat_socket.send(bytes_payload)
	else:
		kernel.heartbeat_socket.send('')
	logger.trace('Ping returned >> %r' % (bytes_payload,))

	# Provide kernel with the option to check for cardiac arrest
	kernel.last_heartbeat = datetime.now()
#	logger.info('Heartbeat    :D ')