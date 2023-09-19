"""
	Implementation of the wire protocol
	
	https://jupyter-client.readthedocs.io/en/latest/messaging.html#wire-protocol

	Rewritten from https://github.com/dsblank/simple_kernel/blob/master/simple_kernel.py
	
	JeroMQ links:
	 - https://github.com/zeromq/jeromq/blob/master/src/main/java/org/zeromq/ZMsg.java
"""
logger = shared.tools.jupyter.logging.Logger()

from shared.tools.jupyter.zmq import ZMsg
from shared.data.types.adhoc import AdHocObject

import json
import hmac, hashlib
from uuid import uuid4
import datetime
from java.nio.charset import Charset

import struct


def sign(key, signature_scheme, entries):
	hmac_payload = hmac.HMAC(key, digestmod=getattr(hashlib, signature_scheme))
	for entry in entries:
		hmac_payload.update(entry)
	return hmac_payload.hexdigest()



def serialize_dictionary(some_dict, assume_ad_hoc=False):
	"""
	Normalized object serialization for messages. 

	This forces adhoc objects to use their interface for dumping contents.
	"""
	if assume_ad_hoc or isinstance(some_dict, AdHocObject):
		if hasattr(some_dict, '_asdict'):
			some_dict = some_dict._asdict()
	
	return json.dumps(some_dict, sort_keys=True, separators=(',',':'),
					  default = lambda obj: repr(obj),
					  ensure_ascii=False, # in case something like 0xFF is in a byte string
		)


def deserialize_dictionary(some_string, make_ad_hoc=False):
	"""
	Normalized object loading.

	Will return an AdHocObject if desired instead of a plain old dictionary.
	"""
	somejson = json.loads(some_string.decode('UTF-8'))
	if make_ad_hoc:
		return AdHocObject(somejson)
	else:
		return somejson



class WireMessage(object):
	"""
	The Wire Protocol, as a message object.

	By default this uses the AdHocObject class to abstract and simplify setting values
	in the message.

	A wire protocol message is packed into a ZMQ message envelope. This class automatically
	generates the needed headers, signatures, and other bits to make this work.

	Note that this is merely the container for the message and has not active
	components. That's in the ContextManagedMessage class.
	"""
	
	_MESSAGE_SPLITTING_DELIMITER_KEY_BETWEEN_IDS_AND_MESSAGE_PROPER = bytes('<IDS|MSG>')
	# note that in Jython the `bytes` part here is completely superfluous, but is technically
	# more correct because we'll be using it to partition the raw bytes in the parser

	STRING_ENCODING = 'UTF-8'
	UTF8_CHARSET = Charset.forName(STRING_ENCODING)
	
	AD_HOC_INTERFACE = True
	
	WIRE_PROTOCOL_VERSION = '5.3'
	
	
	def __init__(self, zMessage=None, key='', signature_scheme='sha256', 
				# initial value overrides, useful as kwargs
				ids=None, header=None, parent_header=None, 
				metadata=None, content=None, raw_data=None,
			):
		"""
		A WireMessage can be started off directly from the payload from a ZMQ message,
		initialized with values, or some combination.
		"""
		if zMessage:
			self.message_parts = []
			id_delim_found = False
			for frame in zMessage:
				if id_delim_found:
					self.message_parts.append(frame.getString(self.UTF8_CHARSET))
				else:
					data = frame.getData()

					try:
						ascii_data = ''.join(chr(x) for x in data)
					except:
						ascii_data = None
					
					if ascii_data == self._MESSAGE_SPLITTING_DELIMITER_KEY_BETWEEN_IDS_AND_MESSAGE_PROPER:
						id_delim_found = True
						self.message_parts.append(self._MESSAGE_SPLITTING_DELIMITER_KEY_BETWEEN_IDS_AND_MESSAGE_PROPER)
					else:
						self.message_parts.append(frame.duplicate())
		else:
			self.message_parts = []
		
		self.key = key if isinstance(key, bytes) else key.encode('ascii') # ('UTF-8')
		
		if signature_scheme.startswith('hmac-'):
			signature_scheme = signature_scheme[5:]
			
		assert signature_scheme in hashlib.algorithms, 'Signature scheme is not in supported list: %r' % (hashlib.algorithms,)
		self.signature_scheme = signature_scheme
		
		# parse and initialize what's been captured first.
		self.parse()
		
		# apply overrides, if any.
		if ids is not None:
			self.ids = [identity for identity in ids]
		if header is not None:
			self.header = header
		if parent_header is not None:
			self.parent_header = parent_header
		if metadata is not None:
			self.metadata = metadata
		if content is not None:
			self.content = content
		if raw_data is not None:
			if isinstance(raw_data, list):
				self._raw_data_buffers = raw_data
			else:
				self._raw_data_buffers = [raw_data]
	
	def __bool__(self):
		# NOTE: consider validating here?
		return self.message_parts is not None
	
	
	def sign(self, entries):
		return sign(self.key, self.signature_scheme, entries)

	@property
	def _signed_contents(self):
		return 	[
				self._serialized_header,
				self._serialized_parent_header,
				self._serialized_metadata,
				self._serialized_content,
			]
	
	@property
	def signature(self):
		return self.sign(self._signed_contents)

	# helper properties to wrap these message fields to make sure they're AdHoc, if desired
	# (that way they can't be set as a dict and then throw errors for being treaded like an object)
	@property
	def header(self):
		return self._header
	@header.setter
	def header(self, header):
		self._header = self._attr_type_interface(header)

	@property
	def parent_header(self):
		return self._parent_header
	@parent_header.setter
	def parent_header(self, parent_header):
		self._parent_header = self._attr_type_interface(parent_header)

	@property
	def content(self):
		return self._content
	@content.setter
	def content(self, content):
		self._content = self._attr_type_interface(content)
	
	@property
	def metadata(self):
		return self._metadata
	@metadata.setter
	def metadata(self, metadata):
		self._metadata = self._attr_type_interface(metadata)
	
	
	# serialization wrappers
	# 
	# these ensure that what goes in and out is a nice, convenient thing and not
	# some binary nonsense that's a pain to deal with.
	@property
	def _serialized_header(self):
		return serialize_dictionary(self.header, self.AD_HOC_INTERFACE)
	@_serialized_header.setter
	def _serialized_header(self, frame_bytes):
		self.header = deserialize_dictionary(frame_bytes, self.AD_HOC_INTERFACE)

	@property
	def _serialized_parent_header(self):
		return serialize_dictionary(self.parent_header, self.AD_HOC_INTERFACE)
	@_serialized_parent_header.setter
	def _serialized_parent_header(self, frame_bytes):
		self.parent_header = deserialize_dictionary(frame_bytes, self.AD_HOC_INTERFACE)

	@property
	def _serialized_metadata(self):
		return serialize_dictionary(self.metadata, self.AD_HOC_INTERFACE)
	@_serialized_metadata.setter
	def _serialized_metadata(self, frame_bytes):
		self.metadata = deserialize_dictionary(frame_bytes, self.AD_HOC_INTERFACE)

	@property
	def _serialized_content(self):
		return serialize_dictionary(self.content, self.AD_HOC_INTERFACE)
	@_serialized_content.setter
	def _serialized_content(self, frame_bytes):
		self.content = deserialize_dictionary(frame_bytes, self.AD_HOC_INTERFACE)

	
	def set_header_defaults(self):
		self.header = self._attr_type_interface({
			'date': datetime.utcnow(), # should include UTC tz
			'msg_id': str(uuid4()),
			'session': str(uuid4()),
			'username': '',
			'msg_type': '',
			'version': self.WIRE_PROTOCOL_VERSION,	
		})
	
	@property
	def _attr_type_interface(self):
		return (AdHocObject if self.AD_HOC_INTERFACE else dict)


	def parse(self):
		"""
		Call this to consume the set message parts and dole them into their
		respective attributes.
		"""
		# initialize empty, though use an AdHocObject for interactive convenience.
		if not self.message_parts:
			self.ids = []
			self.header         = self._attr_type_interface({})
			self.parent_header  = self._attr_type_interface({})
			self.metadata       = self._attr_type_interface({})
			self.content        = self._attr_type_interface({})
			self._raw_data_buffers = []
			return
		
		self.ids = []
		for ix, entry in enumerate(self.message_parts):
			if entry == self._MESSAGE_SPLITTING_DELIMITER_KEY_BETWEEN_IDS_AND_MESSAGE_PROPER:
				break
			if entry:
				self.ids.append(entry)
		
		# validate the message parts
		signature = self.message_parts[ix + 1]
		assert signature == sign(self.key, self.signature_scheme,
								 self.message_parts[ix + 2:]), (
								 	  'Message signature mismatch!' 
								 	+ '\n' + signature
								 	+ '\n' + sign(self.key, self.signature_scheme,
								 					self.message_parts[ix + 2:]))
		
		self._serialized_header         = self.message_parts[ix + 2]
		self._serialized_parent_header  = self.message_parts[ix + 3]
		self._serialized_metadata       = self.message_parts[ix + 4]
		self._serialized_content        = self.message_parts[ix + 5]
		
		#assert signature == self.signature # no need to calculate if already done on raw
		
		if len(self.message_parts) > ix + 5:
			self._raw_data_buffers      = self.message_parts[ix + 6:]
		else:
			self._raw_data_buffers = []

	
	def _add_ids_to_zMessage(self, zMessage):
		if self.ids:
			for entry in self.ids:
				zMessage.add(entry)
		zMessage.add(self._MESSAGE_SPLITTING_DELIMITER_KEY_BETWEEN_IDS_AND_MESSAGE_PROPER)	

	def package(self):
		"""
		Create a ZMQ Message from the contents of this object.

		This will pack the IDs, signature, header, and all the other bits so that it
		is ready to send over the ZMQ wire.
		"""
		zMessage = ZMsg()
		self._add_ids_to_zMessage(zMessage)
		
		signed_contents = self._signed_contents
		
		zMessage.add(self.sign(signed_contents))
		for entry in signed_contents:
			zMessage.add(entry)
		
		for entry in self._raw_data_buffers:
			zMessage.add(entry)
		
		return zMessage
	
	
	def dump(self):
		"""Conveniently hork the contents to a more easily used Python dict."""
		return  {
			'header': self.header,
			'parent_header': self.parent_header,
			'metadata': self.metadata,
			'content': self.content,
		}
		
	def dump_all(self):
		dump = self.dump()
		dump.update({
			'ids': self.ids,
			'raw_data_buffers': self._raw_data_buffers,		
		})
		return dump
		
	def __repr__(self):
		return '<Wire %s>' % (self.header.msg_type,)


def _run_tests():
	# simple examples just to verify basic construction
	from shared.tools.jupyter.wire import WireMessage, ZMsg

	raw_frames = [
		b'd53feddf-67f3-44e9-8b66-229af1719e77', 
		b'<IDS|MSG>', 
		b'b457ab74a4558817ee46ccae8e16f827a36318df28306265effba6c044c247d8', 
		b'{"date":"2023-06-19T05:27:46.261Z","msg_id":"655a24c7-176e-4938-9e0e-47418ba4e6ca",'
		b'"msg_type":"comm_msg","session":"d53feddf-67f3-44e9-8b66-229af1719e77",'
		b'"username":"","version":"5.2"}', 
		b'{}', 
		b'{}', 
		b'{"comm_id":"f6d16cd7-3bb7-4d1b-8148-96c15c1bb976","data":{"method":"request_states"}}']
	
	zMessage = ZMsg()
	for part in raw_frames:
		_ = zMessage.add(part)
	
	kernel_id = '9a298575-e8b55f9fdeca6275b64f585d'
	
	wire_message = WireMessage(zMessage, key=kernel_id)
	
	# verify the loop
	assert repr(zMessage) == repr(wire_message.package())
	
	# test that signature mutation happens
	wire_message.header.username = 'myself'
	
	assert repr(zMessage) != repr(wire_message.package())



#
#from shared.tools.pretty import p,pdir
#from time import sleep
#from shared.tools.thread import async, findThreads
#from shared.tools.logging import Logger
#
#from shared.tools.jupyter.zmq import ZContext, ZMQ, SocketType, ZMsg
#from shared.tools.jupyter.wire import WireMessage
#
#from uuid import uuid4
#import datetime
#
#config = {
#	u'control_port': 32068, 
#	u'ip': '127.0.0.1', 
#	u'transport': 'tcp', 
#	u'shell_port': 32064, 
#	u'stdin_port': 32066, 
#	u'kernel_id': '057e203c-664b-42ac-ab46-cba1e7f652d1', 
#	u'hb_port': 32067, 
#	u'iopub_port': 32065, 
#	u'signature_scheme': 'hmac-sha256', 
#	u'key': '25efe46d-b4a86582e13078bde5455bd0'
#}
#
#
#frames = [
#	'00D70480B4', 
#	'<IDS|MSG>', 
#	'd51ba6de0bc92303a9be60e95e1e25753c9c2ea067f4cdd1974804645e857ab5', 
#	'{"msg_id": "be70a42b-81a7-4790-983b-fcbcea47d7d6_14252_0", "msg_type": "kernel_info_request", '
#	    '"username": "username", "session": "be70a42b-81a7-4790-983b-fcbcea47d7d6", '
#	    '"date": "2023-06-28T05:58:34.523590Z", "version": "5.3"}', 
#	'{}', '{}', '{}',
#]
#
#zMessage = ZMsg()
#for entry in frames:
#	_ = zMessage.add(entry)
#
#wire_message = WireMessage(zMessage, 
#	key=config['key'], 
#	signature_scheme=config['signature_scheme']
#)
#
#
#
#
#
##
##
##
##config =  {
##	"stdin_port": 31526,
##	"control_port": 31924,
##	"hb_port": 30428, #31823,
##	"ip": "127.0.0.1",
##	"ignition_kernel_id": "8c2c",
##	"transport": "tcp",
##	"iopub_port": 31859,
##	"signature_scheme": "hmac-sha256",
##	"shell_port": 31733,
##	"key": "8cae5cd5-65c4-4433-9aea-f574bbc4b5c7"
##}
##
##
##try:
##	zcontext = ZContext()
##	
##	socket = zcontext.createSocket(SocketType.REQ)
##
##	socket.connect('%(transport)s://%(ip)s:%(hb_port)d' % config)
##	
##	socket.send('asdf'.encode('utf-8'))
##	
##	print(socket.recv(0))
##	
###	message = WireMessage(key=config['key'], signature_scheme='sha256',
###				header = {
###					'date': datetime.datetime.utcnow().isoformat()[:23] + 'Z',
###					'msg_id': str(uuid4()),
###					'session': str(uuid4()),
###					'username': 'andrew',
###					'msg_type': 'kernel_info_request',
###					'version': WireMessage.WIRE_PROTOCOL_VERSION,	
###				},
###			)
###	print 'Send: ', message.send(socket)
##except KeyboardInterrupt:
##	pass
##
##
##finally:
##	try:
##		for socket in zcontext.getSockets():
##			zcontext.destroySocket(socket)
##	finally:
##		zcontext.destroy()
##		