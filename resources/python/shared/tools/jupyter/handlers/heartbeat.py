"""
	Heartbeat

	Let Jupyter know we're still here.

	Note that unlike any other role, this socket is used via
	raw bytes and not in a ZMQ Message envelope.

	Regardless, the heartbeat is "send back whatever you got"
	so it doesn't matter terribly much what it says.
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