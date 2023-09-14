"""
	Coordinate and launch the kernel
"""
logger = shared.tools.jupyter.logging.Logger()

from shared.tools.thread import async, Thread, findThreads, getThreadFrame
from shared.tools.logging import Logger
from shared.tools.jupyter.logging import DEFAULT_LOGGING_LEVEL


from random import choice
from uuid import uuid4
from datetime import datetime, timedelta
import string
import json
from time import sleep
import re
import itertools

from org.apache.commons.lang3 import SystemUtils

from shared.data.context.core import Context


from shared.tools.jupyter.messages import KernelMessagingMixin
from shared.tools.jupyter.comm import KernelCommMixin
from shared.tools.jupyter.catch import *
from shared.tools.jupyter.zmq import *
from shared.tools.jupyter.wire import WireMessage
from shared.tools.jupyter.execution.context import ExecutionContext
from shared.tools.jupyter.status import declare_busy, declare_idle, declare_starting


def random_id(length=4):
	return ''.join(choice(string.hexdigits[:16]) for x in range(length))


def re_match_groupdict(pattern, value, flags=0):
	match = re.match(pattern, value, flags)
	if match:
		return match.groupdict()
	else:
		return {}


def re_match_extract(pattern, value, name):
	return re_match_groupdict(pattern, value).get(name)



class CardiacArrest(RuntimeError): pass



class SlotDefaultsMixin(object):

	_SLOT_DEFAULTS = {}
	_SLOT_ALIAS_BRIDGE = {}


	def __init__(self, *init_args, **init_kwargs):
		# set defaults before anything else
		for slot in self.__slots__:
			try:
				setattr(self, slot, init_kwargs.get(slot, 
									init_kwargs.get(self._SLOT_ALIAS_BRIDGE.get(slot, slot),
									self._SLOT_DEFAULTS.get(slot, None))))
			except Exception as error:
				logger.error('Slot failed to get settings: %(slot)r')
				raise error
		super(SlotDefaultsMixin, self).__init__(*init_args, **init_kwargs)
		logger.info('init complete...')



class JupyterKernelCore(
	KernelMessagingMixin,
	KernelCommMixin,
	SlotDefaultsMixin,	
	Context,
	):
	
	_PREP_METHODS = ('init', 'launch', 'tear_down')

	__slots__ = (
		'kernel_name',                 # generic description of kernel type
		'kernel_id',                   # lookup key for reference in Ignition
		'signature_scheme', 'key',     # id/key used by Jupyter (likely same as kernel_id)
		'transport', 'ip', 'zcontext', 
		
		'session', 'username',
		'jupyter_session',
		
		'default_logging_level',
		'live_reload',
		
		'min_port_range', 'max_port_range',
		'loop_delay', 'lingering_delay',
		'interrupted',
		
		'traps', # bucket for signals to trap debug loggers and such
		
		# kernel auto-cleanup when orphaned
		'last_heartbeat', 'cardiac_arrest_timeout',
		
		# holding attributes for core functionality across the five main threads
		'shell_port',    'iopub_port',       'stdin_port',    'control_port',   'heartbeat_port',
		'shell_socket',  'iopub_socket',     'stdin_socket',  'control_socket', 'heartbeat_socket',
						 'iopub_sub_socket', # this is the socket associated with a recv thread, though
		
		# reload requests that the thread replace it's event loop function
		# this helps with hot reloading and development/debug of the kernel itself
		'shell_handler',  'iopub_handler',  'stdin_handler',  'control_handler', 'heartbeat_handler',
		
		# zmq poller contexts to check sockets
		'process_zpoller', 'execution_zpoller',
		'zpoll_timeout_ms', 
		
		# custom message management
		'comms', 'comm_targets',
		
		# convenience functions for auto-resolving so stuff can't get mixed up
		'loggers',
	
	# include the prep methods to allow user overrides
	) + tuple(
		'%s_%s' % (a,b) 
		for a,b 
		in itertools.product(
			('pre', 'post'), 
			_PREP_METHODS)
		)
	
	
	ACTIVE_HANDLER_RELOAD = False
	
	ZMQ_DONTWAIT = ZMQ.DONTWAIT
	
	ZMQ_ROLE_SOCKET_TYPES = {
		'shell'    : SocketType.ROUTER,
		'iopub'    : SocketType.PUB,
		'stdin'    : SocketType.ROUTER,
		'control'  : SocketType.ROUTER,
		'heartbeat': SocketType.REP,
	}
	
	_PROCESS_ROLES = ('heartbeat', 'control',)
	_EXECUTION_ROLES = ('shell', 'iopub', 'stdin',)
	
	_JUPYTER_ROLES = _PROCESS_ROLES + _EXECUTION_ROLES 

	_SLOT_DEFAULTS = {
			'kernel_name': 'ignition_kernel',
			'transport': 'tcp',
			'ip': '*', # '127.0.0.1',
			
			'username': 'kernel',
			
			'signature_scheme': 'hmac-sha256',
			
			'min_port_range': 30000,
			'max_port_range': 32000,
			
			'loop_delay': 0.05,      # seconds
			'lingering_delay': 0.35, # seconds
			
			'zpoll_timeout_ms': 10, # milliseconds
			
			'default_logging_level': DEFAULT_LOGGING_LEVEL,
			'live_reload': False,
			'interrupted': False,
			
			# set to None 
			'cardiac_arrest_timeout': timedelta(minutes=15),
			
			# prime for first load
#           'shell_handler':     'shared.tools.jupyter.handlers.shell.message_handler',
#           'iopub_handler':     'shared.tools.jupyter.handlers.iopub.message_handler',
#           'stdin_handler':     'shared.tools.jupyter.handlers.stdin.message_handler',
#           'control_handler':   'shared.tools.jupyter.handlers.control.message_handler',
#           'heartbeat_handler': 'shared.tools.jupyter.handlers.heartbeat.payload_handler',
			'shell_handler':     shared.tools.jupyter.handlers.shell.message_handler,
			'iopub_handler':     shared.tools.jupyter.handlers.iopub.message_handler,
			'stdin_handler':     shared.tools.jupyter.handlers.stdin.message_handler,
			'control_handler':   shared.tools.jupyter.handlers.control.message_handler,
			'heartbeat_handler': shared.tools.jupyter.handlers.heartbeat.payload_handler,
		
		}

	# allow init_kwargs to use different names (since the kernel standard may not fit my convention)
	# (... and I can't be arsed to rewrite now...)
	_SLOT_ALIAS_BRIDGE = {
		'heartbeat_port': 'hb_port',
		'_identifier': 'kernel_id',
	}

	# default overrides for certain
	for a,b in itertools.product(('pre', 'post'), _PREP_METHODS):
		_SLOT_DEFAULTS['%s_%s' % (a,b)] = lambda kernel: None
	

	# runtime user overrides
	# (unbound, so we grab it, then fire it)
	def _pre_launch(self):
		self.pre_launch(self)
	
	def _post_launch(self):
		self.post_launch(self)
	
	def _pre_init(self):
		self.pre_init(self)
	
	def _post_init(self):
		self.post_init(self)
	
	def _pre_tear_down(self):
		self.pre_tear_down(self)
	
	def _post_tear_down(self):
		self.post_tear_down(self)
	


	def initialize_kernel(self, **init_kwargs):
		
		self.last_heartbeat = datetime.now()
		
		self.traps = {}
			
		self._pre_init()
		
		# the context always has an identifier
		if self.kernel_id is None:
			self.kernel_id = random_id()

		if self.key is None:
			self.key = str(uuid4())
		assert self.key not in JupyterKernel, "Kernel %(kernel_id)s already started!" % self
		
		if self.username is None:
			self.username = SystemUtils.USER_NAME
		
		# ready for comms
		self.comms = {}
		self.comm_targets = {}
		
		self._post_init()


	@property
	def overwatch_thread(self):
		if self._context_threads:
			assert len(self._context_threads) == 1, 'Only one overwatch thread must be active at a time!'
			return list(self._context_threads)[0]
		else:
			return None

	@property
	def session_id(self):
		"""Needed so we can send messages even if there isn't an active session _yet_ (or between them)"""
		if self.session:
			return self.session.id
		else:
			return '' # no session!


	def check_pulse(self):
		if self.cardiac_arrest_timeout:
			if self.last_heartbeat < (datetime.now() - self.cardiac_arrest_timeout):
				self.logger.warn('Cardiac arrest!')
				raise CardiacArrest


	def tear_down(self):
		try:
			self._pre_tear_down()
			
			self.logger.info('Tearing down kernel %(kernel_id)s...' % self)
			
			if self.session:
				self.session.destroy()
			
			if self.zcontext.isEmpty() and self.zcontext.isClosed():
				self.logger.warn('ZContext for already emptied and closed')
				return
			
			try:
				self.logger.info('Closing poller...')
				self.zpoller.destroy()
				
				self.logger.info('Destroying sockets...')
				for socket in self.zcontext.getSockets():
					self.zcontext.destroySocket(socket)
				
				for attr in [attr for attr in self.__slots__ if attr.endswith('_port') or attr.endswith('_socket')]:
					setattr(self, attr, None)
			
			finally:
				self.logger.debug('Destroying zcontext...')
				self.zcontext.destroy()
			
				self.logger.info('Done. Good-bye!')
		finally:
			self._post_tear_down()



	def launch_kernel(self):
		self._pre_launch()
		
		if self.ACTIVE_HANDLER_RELOAD:
			self.reload_handlers()
	
		assert not self.is_launched, "ZContext already launched! HCF >_<"
		self.zcontext = ZContext()
		
		for role in self._JUPYTER_ROLES:
			# create sockets
			socket = self.zcontext.createSocket(self.ZMQ_ROLE_SOCKET_TYPES[role])
			
			self[role + '_socket'] = socket
			
			# if not explicitly requested by kernel startup,
			# then bind each to a random port (a connection file may have been
			# provided that declared what ports to use, so use those if set)
			if self[role + '_port'] is None:
			   self[role + '_port'] = self.bind_random_port(self[role + '_socket'])
			else:
			   self.bind_selected_port(self[role + '_socket'], self[role + '_port'])
			self.logger.trace('%-16s on port %d' % (role, self[role + '_port']))
		
		declare_starting(self)

		# control and heartbeat have a dedicated poller to ensure kernel can't be blocked
		self.process_zpoller = ZPoller(self.zcontext)
		for socket in self.process_sockets:
			self.process_zpoller.register(socket, ZPoller.POLLIN)

		# shell, iopub, and stdin are bundled for the actual remote execution
		self.execution_zpoller = ZPoller(self.zcontext)
		for socket in self.execution_sockets:
			self.execution_zpoller.register(socket, ZPoller.POLLIN)

		self.new_execution_session()

		# start the zmq socket polling
		self.poll_process()
		self.poll_execution()
		
		sleep(0.25)
		
		self._post_launch()
		
		declare_idle(self)



	def new_execution_session(self):
		self.session = ExecutionContext(self)
		try:
			self.heartbeat_socket.send('restart')
		except:
			pass # maybe not set up yet


	@property
	def process_sockets(self):
		return [self[role + '_socket'] for role in self._PROCESS_ROLES]

	
	@property
	def execution_sockets(self):
		return [self[role + '_socket'] for role in self._EXECUTION_ROLES]



	@Context.poll('process')
	def poll_process(self):
		with ZmqErrorCatcher(self) as catcher:
			self.process_zpoller.poll(self.zpoll_timeout_ms)        
			for role, socket in zip(self._PROCESS_ROLES, self.process_sockets):
				if self.process_zpoller.isReadable(socket):
					# heartbeat is the only raw payload that isn't a message
					if role == 'heartbeat':
						self._handle_zbytes(role, socket)
					else:
						self._handle_zmessage(role, socket)


	@Context.poll('execution')
	def poll_execution(self):
		with ZmqErrorCatcher(self) as catcher:
			self.execution_zpoller.poll(self.zpoll_timeout_ms)        
			for role, socket in zip(self._EXECUTION_ROLES, self.execution_sockets):
				if self.execution_zpoller.isReadable(socket):
					self._handle_zmessage(role, socket)


	def reload_handlers(self):
		for role in self._JUPYTER_ROLES:
			self[role + '_handler'] = reload_function(self[role + '_handler'])
	
	
	@property
	def now(self):
		# TODO: should include UTC tz object
		return datetime.utcnow().isoformat()[:23] + 'Z'
	
	
	@property
	def is_launched(self):
		return not (self.zcontext is None or self.zcontext.isClosed())
	
	@property
	def is_interrupted(self):
		self.check_pulse()
		return self.interrupted
	
	
	def bind_random_port(self, socket):
		return socket.bindToRandomPort(
				'%(transport)s://%(ip)s' % self, 
				self.min_port_range,
				self.max_port_range,
			)

	def bind_selected_port(self, socket, port):
		socket.bind(('%%(transport)s://%%(ip)s:%d' % port) % self)



	@property
	def connection_file(self):
		return json.dumps(self.connection_info, indent=2,)
	
	@property
	def connection_info(self):
		return {
			'transport': self.transport,
			'ip': self.ip,
			
			'ignition_kernel_id': self.ignition_kernel_id,
			
			'signature_scheme': self.signature_scheme,
			'key': self.key,
			
			'shell_port':   self.shell_port,
			'iopub_port':   self.iopub_port,
			'stdin_port':   self.stdin_port,
			'control_port': self.control_port,
			'hb_port':      self.hb_port,
		}
	
	
	# PROPERTIES OF SHAME
	# Wherein I couldn't be arsed to refactor and just let there be two names for something.
	@property
	def hb_port(self):
		return self.heartbeat_port
	
	@hb_port.setter
	def hb_port(self, new_port):
		self.heartbeat_port = hb_port


	@property
	def ignition_kernel_id(self):
		return self.kernel_id
	
	@ignition_kernel_id.setter
	def ignition_kernel_id(self, new_kernel_id):
		self.kernel_id = new_kernel_id




class JupyterKernel(
	JupyterKernelCore,
	):

	_INITIAL_LOGGING_LEVEL = DEFAULT_LOGGING_LEVEL
	_LOGGER_CLASS = Logger
	
	_CONTEXT_THREAD_ROLE = 'overwatch'
	
	_THREAD_NAME_SEPARATOR = ':' # avoid '-' because of UUID identifiers
	
	_EVENT_LOOP_DELAY = 0.01 # seconds
	_THREAD_DEATH_LOOP_WAIT = 0.1 # seconds

#	def __init__(self, kernel_id=None, *args, **kwargs):
#		kwargs['identifier'] = kernel_id
#		super(JupyterKernel, self).__init__(*args, **kwargs)


	def initialize_context(self, *init_args, **init_kwargs):
		self.initialize_kernel(*init_args, **init_kwargs)
		self.identifier = self.kernel_id

	def launch_context(self):
		self.launch_kernel()

	def poll_context(self):
		if self.is_interrupted:
			self.logger.info('Kernel interrupt set. Raising interrupt...')
			raise KeyboardInterrupt('Kernel interrupted. Raising interrupt...')

	def finish_context(self):
		self.tear_down()

	def crash_context(self):
		self.tear_down()




def spawn_kernel(**kernel_init_kwargs):
	if not kernel_init_kwargs:
		kernel_init_kwargs['kernel_id']= random_id()
	
	try:
		kernel = JupyterKernel(**kernel_init_kwargs)
		kernel.start_loop()
		return kernel
	except:
		raise RuntimeError("Kernel likely failed to start. Check logs.")
		return None




def reload_function(function):
	"""Return the most recent live version of function. 
	Can be the original function or the import path string to get it.
	
	Imports may be cached, and direct references may not update during execution.
	This grabs the reference straight from the horse's mouth.
	
	TODO: may need project scope access to work (i.e. from webdev)
	"""
	# resolve the thing to refresh
	if isinstance(function, (str, unicode)):
		module_path, _, function_name = function.rpartition('.')
	else:
		module_path = function.func_code.co_filename[1:-1].partition(':')[2]
		function_name = function.func_code.co_name
	# get system context
	context = shared.tools.meta.getIgnitionContext()
	script_manager = context.getScriptManager()
	current_scripting_state = script_manager.createLocalsMap()
	# resolve the function again
	import_parts = module_path.split('.')
	thing = current_scripting_state[import_parts[0]]
	for next_module in import_parts[1:]:
		try:
			thing = thing.getDict()[next_module]
		except AttributeError:
			thing = getattr(thing, next_module)
	return getattr(thing, function_name)





## script playground context
#from shared.tools.pretty import p,pdir,install;install()
#try:
#	print 'Kernel %r state: %r' % (kernel_id, kernel_context['threads']['hub'].getState())
#except NameError:
#	from shared.tools.jupyter.core import spawn_kernel, get_kernel_context
#	from time import sleep
#	kernel_id = spawn_kernel()
#	sleep(0.25)
#	kernel_context = get_kernel_context(kernel_id)
#	scram = lambda kernel_context=kernel_context: kernel_context['threads']['hub'].interrupt()