from shared.tools.thread import async
from shared.tools.global import ExtraGlobal
from shared.tools.error import formatted_traceback

import BaseHTTPServer
from cgi import escape
import urlparse
import urllib

import sys
import re
import base64
import json

from java.lang import Exception as JavaException
from org.apache.commons.lang3.exception import ExceptionUtils



def check_basic_authentication(authorization_header, user_source=None):
	assert authorization_header.startswith('Basic ')
	auth = base64.b64decode(authorization_header[6:])
	username, _, password = auth.partition(':')
	if user_source is None:
		# if none is given, try each
		for user_source in system.user.getUserSources():
			if system.security.validateUser(username, password, user_source.getName()):
				return True
		else:
			return False
		
	else:
		return system.security.validateUser(username, password, user_source)



class SimpleServer(BaseHTTPServer.HTTPServer):
	allow_reuse_address = True

	def handle_error(self, request, client_address):
		exc_type, exc_val, exc_tb = sys.exc_info()
		system.util.getLogger('Sidecar').error('Error with %r: %r to [%r]\n%s' %(
			self, request, client_address, formatted_traceback(exc_val, exc_tb),
		))



class SimpleREST(BaseHTTPServer.BaseHTTPRequestHandler):

	@property
	def logger(self):
		#		frame = sys._getframe()
		#		while frame:
		#			match = re.match(r'_?do_(?P<method>[A-Z]+)', frame.f_code.co_name)
		#			if match:
		#				method = match.groupdict()['method']
		#				break
		#			frame = frame.f_back
		return shared.tools.logging.Logger(type(self).__name__, prefix='[%s] ' % (self.command,))

	def __getitem__(self, attribute):
		"""Make this dict-like to simplify things a bit."""
		try:
			return getattr(self, attribute)
		except AttributeError:
			raise KeyError('%s is not available for this handler')


	@staticmethod
	def html_escape(some_string):
		return escape(some_string.decode('utf8'))

	_PAYLOAD_CONVERTERS = {
		'text/plain': lambda x: x,
		'application/json': system.util.jsonDecode,
		'text/json': system.util.jsonDecode,
		'/form-data': urlparse.parse_qs,
	}
	
	try:
		_PAYLOAD_CONVERTERS['application/yaml'] = shared.data.yaml.core.safe_load
		_PAYLOAD_CONVERTERS['text/yaml'] = shared.data.yaml.core.safe_load
	except AttributeError:
		pass # yaml unavailable


	def drain_payload(self):
		try:
			payload_bytes = int(self.headers['Content-Length'])
		except:
			self._payload = None
			return None
		
		raw_payload = self.rfile.read(payload_bytes)
		
		try:
			decoder = self._PAYLOAD_CONVERTERS[self.headers['Content-Type']]
		except KeyError:
			raise NotImplementedError('Content type not supported: %(Content-Type)s' % self.headers)
		
		self._payload = decoder(raw_payload)
		return self._payload

	@property
	def query(self):
		return urlparse.urlsplit(self.path)[3]

	@property
	def params(self):
		try:
			paramdict = urlparse.parse_qs(self.query)
			return dict( ( key,
					   value[0] if isinstance(value, list) and len(value) == 1 else value
					 )
						 for key, value
						 in paramdict.items())
		except:
			params = {}
			for entry in self.query.split('&'):
				key,_,value = entry.partition('=')
				params[urllib.unquote(key)] = urllib.unquote(value)
			return params

	@property
	def payload(self):
		try:
			return self._payload
		except:
			return None

	@property
	def endpoint(self):
		return urlparse.urlsplit(self.path)[2]


	def _pack_response(self, response, content_type=None):
		if content_type:
			self.send_header('Content-Type', content_type)
			# assume that if the content type is provided, it's already a byte array/stream
			# so get it's byte length
			if response is not None:
				self.send_header('Content-Length', len(response))
		elif response is None:
			pass
		elif isinstance(response, (tuple, list, dict)):
			#response = system.util.jsonEncode(response, 2)# .encode('utf-8') # <== fails on lists
			response = json.dumps(response,indent=2)
			self.send_header('Content-Type', 'application/json')
			self.send_header('Content-Length', len(response))
		elif isinstance(response, (str, unicode)):
			if re.match(r'\W*(<html[ >]|<!DOCTYPE html ).*', response, re.I):
				self.send_header("Content-Type", "text/html")
			else:
				self.send_header("Content-Type", "text/plain")
			self.send_header('Content-Length', len(response))
		elif isinstance(response, (Exception,)):
			self._pack_response(repr(error))
			return
		else:
			raise NotImplementedError('Content reply type not supported: %r' % (type(response),))
		
		self.end_headers()
		if response is not None:
			self.wfile.write(response)


	def handle_reply(self, response):
		self.send_response(200)
		self._pack_response(response)

	def handle_exception(self, exception_type, exception, exception_traceback):
		self.send_response(400)
		if isinstance(exception, Exception):
			import traceback
			stacktrace = ''.join(
				traceback.format_exception(exception_type, exception, exception_traceback)
			)
		elif isinstance(exception, JavaException):
			stacktrace = ExceptionUtils.getStackTrace(exception)
		else:
			stacktrace = repr(exception)
		self.logger.error(stacktrace)
		self._pack_response(stacktrace)


	def do_HEAD(self):
		if 'authorization' in self.headers:
			assert check_basic_authentication(self.headers['authorization'])
		try:
			self._do_HEAD()
		except Exception as error:
			self.send_response(400)
		self.send_response(200)

	def do_GET(self):
		if 'authorization' in self.headers:
			assert check_basic_authentication(self.headers['authorization'])
		try:
			response = self._do_GET()
		except Exception as error:
			self.handle_exception(*sys.exc_info())
			return
		self.handle_reply(response)

	def do_POST(self):
		if 'authorization' in self.headers:
			assert check_basic_authentication(self.headers['authorization'])	
		self.drain_payload()
		try:
			response = self._do_POST()
		except Exception as error:
			self.handle_exception(*sys.exc_info())
			return
		self.handle_reply(response)

	def do_PUT(self):
		if 'authorization' in self.headers:
			assert check_basic_authentication(self.headers['authorization'])	
		self.drain_payload()
		try:
			response = self._do_PUT()
		except Exception as error:
			self.handle_exception(*sys.exc_info())
			return
		self.handle_reply(response)

	def do_DELETE(self):
		if 'authorization' in self.headers:
			assert check_basic_authentication(self.headers['authorization'])	
		try:
			response = self._do_DELETE()
		except Exception as error:
			self.handle_exception(*sys.exc_info())
			return
		self.handle_reply(response)


	def _do_HEAD(self):
		return

	def _do_GET(self):
		return None

	def _do_POST(self):
		return None

	def _do_PUT(self):
		return None

	def _do_DELETE(self):
		return None


try:
	from shared.data.context.core import Context
	
	class SidecarContext(Context):
	
		DISALLOWED_PORTS = set([
			80, 443, 8088, 8043, 8060, 8090, 
		])
		_MINIMUM_PORT = 7000
		_DEFAULT_RANGE = slice(8100, 8700)
		PORTS_IN_USE = set()
		
		# context settings
		_EVENT_LOOP_DELAY = 0.01 # seconds
		_INITIAL_LOGGING_LEVEL = 'debug'
		
		
		def initialize_context(self, http_handler, port=None, hostname='localhost'):
			# validate the port
			self._select_port(port)
			self.identifier = self.port
			
			# set the host
			self.hostname = hostname
			
			self._http_handler = http_handler
			
			# start up the service
			self.httpd = SimpleServer((self.hostname, self.port), self._http_handler)
			
			
		def launch_context(self):
			self.logger.info('{self._http_handler} sidecar starting up on {self.hostname}:{self.port}')
			
			# start the request loop
			self.handle_requests()
		
		def poll_context(self):
			pass
		
		def finish_context(self):
			self.stop_server()
	
		def crash_context(self):
			self.stop_server()
			
		def stop_server(self):
			self.httpd.server_close()
			self._release_port()
		
		@Context.poll('requests')
		def handle_requests(self):
			self.httpd.handle_request()
	
	
		def _select_port(self, port):
			if port is None:
				self._select_port(self._DEFAULT_RANGE)
				return
			elif isinstance(port, slice):
				port_span = port
				for i in range(100):
					port = random.randint(port_span.start, port_span.stop)
					if self.is_port_valid(port):
						break
				else:
					raise RuntimeError('A valid port was not quickly selected for %r.' % (port_span,))
			elif isinstance(port, int):
				assert self.is_port_valid(port), 'Port given is not available: %r' % (port,)
			else:
				raise ValueError('Port not valid: %r' % (port,))
			self.PORTS_IN_USE.add(port)
			self.port = port
		
		def _release_port(self):
			self.PORTS_IN_USE.remove(self.port)
			
	
		def is_port_valid(self, port):
			return not any([
				port < self._MINIMUM_PORT,
				port in self.DISALLOWED_PORTS,	
				port in self.PORTS_IN_USE,
			])

except ImportError:
	pass # no sidecar context management :C


def shutdown(port):
	session = ExtraGlobal.setdefault(port, 'Sidecar', {})
	session['shutdown'] = True



@async(name='Sidecar-REST')
def launch_sidecar(port, RestHandler, 
		hostname='localhost', 
		resume_session=True, 
		session_timeout=600
	):
	"""
	This assumes that keep_running() is a function of no arguments which
	is tested initially and after each request.  If its return value
	is true, the server continues.
	"""
	system.util.getLogger('Sidecar').info("Launching sidecar on port %r with %r" % (port, RestHandler))

	if resume_session:
		session = ExtraGlobal.setdefault(port, 'Sidecar', {}, lifespan=session_timeout)
	else:
		ExtraGlobal.stash({}, port, 'Sidecar', lifespan=session_timeout)
		session = ExtraGlobal.access(port, 'Sidecar')

	server_address = (hostname, port)
	httpd = SimpleServer(server_address, RestHandler)
	try:
		system.util.getLogger('Sidecar').info('Sidecar started at http://%s:%r' % (hostname, port,))

		while not ExtraGlobal.setdefault(port, 'Sidecar', {}, lifespan=session_timeout).get('shutdown', False):
			httpd.handle_request()
	except Exception, error:
		system.util.getLogger('Sidecar').info("Exception on port %r: %s %r" % (port,type(error), error))

	except:
		pass
	finally:
		#print 'Shutting down %r' % (httpd.server_address,)
		httpd.server_close()
		ExtraGlobal.trash(port, 'Sidecar') # clear session
		#print '... done!'
		system.util.getLogger('Sidecar').info("Sidecar torn down from port %r" % (port,))
