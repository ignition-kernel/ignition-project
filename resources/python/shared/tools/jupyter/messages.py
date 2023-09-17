"""
	Make message details a bit easier to work with.
	
	ContextManagedMessage means that a socket can be given and, if set,
	the context management bits will automatically send the message on exit.
	
	For example, here's how the status update is sent:
		
		with kernel.iopub_broadcast('status', message) as update:
			update.content.execution_state = status

	AdHocObjects are what let the content of the message get set in an arbitrary way.
"""
logger = shared.tools.jupyter.logging.Logger()


__all__ = ['KernelMessagingMixin']


from shared.tools.jupyter.wire import WireMessage
from shared.tools.jupyter.zmq import SocketType, ZMsg
from shared.tools.jupyter.status import declare_busy, declare_idle

from uuid import uuid4


class ContextManagedMessage(WireMessage):
	
	def __init__(self, zMessage=None, key='', signature_scheme='sha256', 
		# initial value overrides, useful as kwargs
		ids=None, header=None, parent_header=None, 
		metadata=None, content=None, raw_data=None,
	
		topic_prefix='',       # can take the place of ids on broadcast
		topic_broadcast=False, # broadcast instead of target socket IDs
		socket=None,
		):
		super(ContextManagedMessage, self).__init__(zMessage, key, signature_scheme,
				ids, header, parent_header, metadata, content, raw_data,
			)
		
		self.target_socket = socket
		
		# for use in broadcast, prepends message type with this
		self.topic_prefix = topic_prefix
		self.topic_broadcast = topic_broadcast

	def _add_ids_to_zMessage(self, zMessage):
		"""Override so topics may be broadcast (like for IOPub)"""
		if self.topic_broadcast:
			zMessage.add(self.topic_prefix + self.header.msg_type)
		else:
			if self.ids:
				for entry in self.ids:
					zMessage.add(entry)
		zMessage.add(self._MESSAGE_SPLITTING_DELIMITER_KEY_BETWEEN_IDS_AND_MESSAGE_PROPER)	
	
	def __enter__(self):
		return self
	
	def __exit__(self, exc_type, exc_val, exc_tb):
		if self.target_socket:
			self.send()

	def send(self, socket=None):
		"""Send message to target"""
		if socket is None:
			socket = self.target_socket
		assert socket
		
		zMessage = self.package()
		
		try:
			assert zMessage.send(socket)
		except Exception as error:
			raise error
		finally:
			zMessage.destroy()



class KernelMessagingMixin(object):
	"""
	Consolidate the messaging bits for the kernel in one place.

	First are the bits for sending messages, and then the message
	handling bits.
	"""
	# SENDING
	
	def _new_message(self, msg_type, target_socket=None, origin_message=None, topic_broadcast=False):
		return ContextManagedMessage(
			key = self.key,
			header = {
				'date': self.now,
				'msg_id': str(uuid4()),
				'session': self.session_id,
				'username': self.username,
				'msg_type': msg_type,
				'version': WireMessage.WIRE_PROTOCOL_VERSION,	
			},
			parent_header = origin_message.header if origin_message else None,
			# default to a direct reply
			ids = origin_message.ids if origin_message else None,
			# in case message is for broadcast on a topic (like IOPub)
			topic_prefix = 'kernel.%(kernel_id)s.' % self,
			topic_broadcast = topic_broadcast,
			socket = target_socket,
		)
	
	# most messages on IOPub will be broadcast based on the topic
	def iopub_broadcast(self, msg_type, origin_message=None):
		return self._new_message(msg_type, self.iopub_socket, origin_message, topic_broadcast=True)
	
	# ensure replies for messages are handled and sent back to the requester
	def iopub_message(self, msg_type, origin_message=None):
		return self._new_message(msg_type, self.iopub_socket, origin_message, topic_broadcast=False)
	
	def shell_message(self, msg_type, origin_message=None):
		return self._new_message(msg_type, self.shell_socket, origin_message)	
	
	def control_message(self, msg_type, origin_message=None):
		return self._new_message(msg_type, self.control_socket, origin_message)	
	
	def stdin_message(self, msg_type, origin_message=None):
		return self._new_message(msg_type, self.stdin_socket, origin_message)	

	# RECIEVING
	
	def _handle_zmessage(self, role, socket):
		"""
		Consume a ZMQ message off the socket, if any, and then handle it based on the role.
		"""
		zMessage = ZMsg.recvMsg(socket, self.ZMQ_DONTWAIT)
		if zMessage is not None:
			message = WireMessage(zMessage, 
					  key=self.key, 
					  signature_scheme=self.signature_scheme
				)
			try:
				declare_busy(self, message)
				if self.ACTIVE_HANDLER_RELOAD:
					reload_function(self[role + '_handler'])(self, message)
				else:
					self[role + '_handler'](self, message)
				zMessage.destroy()
			finally:
				declare_idle(self, message)

	def _handle_zbytes(self, role, socket):
		"""
		Handle socket data as raw bytes.

		This is only used by the heartbeat role.
		"""
		payload = socket.recv(self.ZMQ_DONTWAIT)
		self[role + '_handler'](self, payload)
