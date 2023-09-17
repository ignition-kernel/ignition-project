"""
	REST API Endpoints for kernel control

	The interaction here is generalized because Designer sessions
	don't have WebDev. So while it's straightforward and convenient
	to use WebDev for accessing gateway context, we gotta do things
	the hard way for making Jupyter available to a Designer session.

	See .core for more in-depth explanations of the @rest decorator.
"""
logger = shared.tools.jupyter.logging.Logger()

from shared.tools.jupyter.core import JupyterKernel, spawn_kernel

from shared.tools.jupyter.handlers.web.core import SimpleREST, rest

import re
import signal


def url_match(pattern, url, flags=0):
	match = re.match(pattern, url, flags)
	if not match:
		return tuple(), {}
	else:
		return match.groups(), match.groupdict()

def extract_kernel_id(url):
	return url_match(r'.*/kernel(?:/(?P<kernel_id>[a-z0-9-]+))?', url, re.I)[1]['kernel_id']


@rest
def doHead(path):
	"""Verify if kernels are still alive"""
	assert path[1:], "HEAD requires a kernel to poll."
	
	kernel_id = request["remainingPath"][1:]
	_ = JupyterKernel[kernel_id]


@rest
def doGet(path):
	"""Retrieve/list kernel info"""
	kernel_id = extract_kernel_id(path)
	
	if kernel_id:
		return JupyterKernel[kernel_id].connection_file
	else:
		return [kernel.kernel_id for kernel in JupyterKernel]


@rest
def doPost(payload):
	"""Launch and configure kernels"""
	logger.trace(payload)
	
	try:
		kernel_id = payload['kernel_id']
		kernel = JupyterKernel[kernel_id]
		logger.warn('Kernel already running: [%(kernel_id)s]' % kernel)
	except KeyError:
		kernel = spawn_kernel(**payload)
		logger.info('Launched [%(kernel_id)s]' % kernel)
		logger.info('Kernel info: %r' % (kernel.connection_info,))
	
	for key, value in payload.items():
		if not kernel[key] == value:
			logger.warn('Kernel [%s] config mismatch on %s: %r vs %r' % (
							kernel.kernel_id, key, value, kernel[key]))
	
	return kernel.connection_info


@rest
def doDelete(path, payload):
	"""Scram kernels"""
	kernel_id = extract_kernel_id(path)
	
	signum = payload.get('signal')

	try:
		if kernel_id and signum is not None:
			# the termination request is for the kernel's execution context
			# so we'll keep this one up, but replace the excon
			if signum in (0, signal.SIGTERM):
				JupyterKernel[kernel_id].new_execution_session()
				return
	except KeyError:
		return # kernel missing, but this is a DELETE so that's probably ok, even on a restart
	
	if kernel_id:
		logger.warn('DELETE Request made to scram %s' % (kernel_id,))
		try:
			JupyterKernel.SCRAM(kernel_id)
			return {'scrammed': [kernel_id]}
			# return 'Kernel [%s] scrammed.' % (kernel_id,)
		except KeyError:
			return {'scrammed': []}
			# return 'FAILED: Kernel [%s] not found or already scrammed!' % (kernel_id,)
	else:
		logger.error('DELETE Request made to scram ALL kernels')
		scrammed_kernels = [
			kernel.kernel_id 
			for kernel 
			in shared.tools.jupyter.core.JupyterKernel
		]
		JupyterKernel.SCRAM_ALL()
		return {'scrammed': scrammed_kernels}



class KernelREST(SimpleREST):
	
	def _do_HEAD(self):
		doHead(self.path)
	
	def _do_GET(self):
		return doGet(self)
	
	def _do_POST(self):
		return doPost(self)
	
	def _do_DELETE(self):
		return doDelete(self)




def launch_designer_kernel_management(port=8989):
	from shared.tools.sidecar import SidecarContext
	sidecar = SidecarContext(KernelREST, 8989)
	_ = sidecar.start_loop()

