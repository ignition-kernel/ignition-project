"""
	Handlers for the REST API
	
	This will normally run via WebDev, but if not installed this will
	bootstrap a listener. And for designers it'll connect via this.
	

"""
logger = shared.tools.jupyter.logging.Logger()

from shared.tools.meta import PythonFunctionArguments
from shared.tools.sidecar import SimpleREST, BaseHTTPServer
import functools
import urlparse




# simple shimming to make methods easily compatible with WebDev

WEBDEV_REQUEST_TRANSLATOR = {
	# this is not remainingPath - this is meant to useful for route handling, if somehow used
	'path': lambda request: urlparse.urlsplit(str(request['servletRequest'].getRequestURL()))[2],
	'payload': lambda request: request.get('data') or {},
	'params': lambda request: request.get('params') or {},
	'headers': lambda request: request.get('headers', {}),
}

AVAILABLE_REST_DETAILS = {
	'path', 'payload', 'params', 'headers', # 'session',
}

assert set(WEBDEV_REQUEST_TRANSLATOR) >= AVAILABLE_REST_DETAILS


def is_webdev_request(endpoint_info):
	try:
		# very naive heuristic
		if 'servletResponse' in endpoint_info:
			return True
	except:
		pass
	return False



def rest(function):
	"""
	Decorator. Simplifies and abstracts the calling convention so that it can be called
	with either sidecar's class or with the WebDev response bits.
	"""
	pfa = PythonFunctionArguments(function)
	assert AVAILABLE_REST_DETAILS >= set(pfa.args), '@rest decorator only covers these arguments: %r' % (AVAILABLE_DETAILS,)

	@functools.wraps(function)
	def normalized_rest_call(request_info=None, **overrides):
		kwargs = {}
		if request_info is None:
			assert set(overrides) >= set(pfa.args), 'Without a request object, overrides must be provided to fulfill the function: %r needs %r' % (function, pfa.args)
		elif isinstance(request_info, BaseHTTPServer.BaseHTTPRequestHandler):
			kwargs = {arg: request_info[arg] for arg in pfa.args}
		elif is_webdev_request(request_info):
			kwargs = {arg: WEBDEV_REQUEST_TRANSLATOR[arg](request_info) for arg in pfa.args}
		else:
			raise NotImplementedError('Not sure what to make of this request format %r' % (request_info,))
		for arg in pfa.args:
			if not arg in overrides:
				continue
			kwargs[arg] = overrides[arg]
		return function(**kwargs)
	
	return normalized_rest_call






