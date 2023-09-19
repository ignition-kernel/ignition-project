"""
	Funnel data into and out of Ignition

	This is a placeholder for adding functionality for firehosing
	data across ZMQ sockets into external Python libraries like 
	Pandas or NumPy/SciPy.

	It might end up being self-contained or maybe a special case
	of kernel context.
"""


#
#
#class DataBus(object):
#	"""
#	Holding context for the PUB/SUB setup
#	"""
#	
#	
#	def __init__(self, pub_socket_port=None, sub_socket_port=None):
#		
#				
#		
#		
#		 
#	
#	
#	def setup_context(self):
#		self.zcontext= ZContext()
#		self.pub_socket = self.zcontext.createSocket(SocketType.PUB)
#		self.sub_socket = self.zcontext.createSocket(SocketType.SUB)
#		
#		
#	def tear_down(self):
#		
#	
#		
#	def bind_random_port(self, socket):
#		return socket.bindToRandomPort(
#				'%(transport)s://%(ip)s' % self, 
#				self.min_port_range,
#				self.max_port_range,
#			)
#
#	def bind_selected_port(self, socket, port):
#		socket.bind(('%%(transport)s://%%(ip)s:%d' % port) % self)