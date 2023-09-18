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
import sys

from org.apache.commons.lang3 import SystemUtils

from shared.data.context.core import Context


from shared.tools.jupyter.base import JupyterKernelBaseMixin
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
	"""
	Allows default values to be configured for all slots before initializing.
	"""
	_SLOT_DEFAULTS = {}
	_SLOT_ALIAS_BRIDGE = {}


	def __init__(self, *init_args, **init_kwargs):
		# collect the defaults from each base class
		# (this is probably more appropriately in the metaclass, defined at subclass
		#  creation, but I didn't want to get in the way of how the context did things)
		slot_aliases = {}
		slot_defaults = {}
		for base_class in reversed(type(self).__mro__):
			for d, bcattr in zip((slot_defaults, slot_aliases,), 
								 ('_SLOT_DEFAULTS', '_SLOT_ALIAS_BRIDGE',)):
				d.update(getattr(base_class, bcattr, {}))
		# set defaults before anything else
		for slot in self.__slots__:
			try:
				setattr(self, slot, init_kwargs.get(slot, 
									init_kwargs.get(slot_aliases.get(slot, slot),
									slot_defaults.get(slot, None))))
			except Exception as error:
				raise error
		super(SlotDefaultsMixin, self).__init__(*init_args, **init_kwargs)



class JupyterKernelCore(
	KernelMessagingMixin,
	KernelCommMixin,
	SlotDefaultsMixin,	
	Context,
	JupyterKernelBaseMixin,
	):
	"""
	The Kernel.

	For context and thread management bits, see the Context class definition.
	For message handling, see KernelMessagingMixin.
	For Comms management, see KernelCommMixin.

	This class sets the values available to the kernel itself as well as all the 
	data shared between the context's roles.

	Generally, there's two roles to track:
	 - execution performs the work revolving around the Python code execution.
	   It tracks the shell commands, iopub updates, and consuming stdin socket data.
	 - process performs the work on the kernel itself.
	   Generally that means interrupting the execution thread when needed and covers
	   the control and heartbeat roles.

	This class does not directly override and complete the Context methods needed.
	That's more cleanly indicated by the JupyterKernel class.

	

	"""
	_PREP_METHODS = ('init', 'launch', 'tear_down')

	__slots__ = (
		'kernel_name',                 # generic description of kernel type
		'kernel_id',                   # lookup key for reference in Ignition
		'signature_scheme', 'key',     # id/key used by Jupyter (likely same as kernel_id)
		'transport', 'ip', 'zcontext', 
		'_server_public_key', '_server_secret_key', # for encrypting sockets
		
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
	_KERNEL_KEYS = {}
	
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
		"""
		Set up all the things the kernel needs to get started without actually starting.
		"""
		
		self.last_heartbeat = datetime.now()
		
		# set up for general use, but really, traps shouldn't be in use anywhere.
		# just a handy bucket
		self.traps = {}
		
		# run any user-defined pre-init setup
		self._pre_init()

		# allow base classes to initialize their own bits
		super(KernelCommMixin, self).initialize_kernel(**init_kwargs)

		# the context always has an identifier
		if self.kernel_id is None:
			self.kernel_id = random_id()

		# used for validating and signing messages
		# NOTE: .key does NOT encrypt - it's merely a shared key with the Jupyter kernel
		#       manager so that both the kernel and Jupyter can trust the message contents
		#       have not been tampered with.
		# The key is typically given over a secure line (the kernel provisioner shares it,
		#       so for trust, be sure to share over a secure line like HTTPS!)
		if self.key is None:
			self.key = str(uuid4())
		assert self.key not in JupyterKernel, "Kernel %(kernel_id)s already started!" % self
		
		if self.username is None:
			self.username = SystemUtils.USER_NAME
		
		# set up encryption
		# (only generate once per kernel)
		if not self.kernel_id in self._KERNEL_KEYS:
			curve = Curve()
			self._KERNEL_KEYS[self.kernel_id] = curve.keypairZ85()
		self._server_public_key, self._server_secret_key = self._KERNEL_KEYS[self.kernel_id]

		# cooperate on initialization, in case it's used
		super(JupyterKernelCore, self).initialize_kernel(**init_kwargs)
		
		self._post_init()


	@property
	def overwatch_thread(self):
		# I called the context thread "overwatch" and never really stopped. So.
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
		# NOTE: this doesn't necessarily kill the kernel, it just lets the kernel
		# know that Jupyter is no longer in contact with it!
		# Under normal operations this would likely just leave it running and reconnect
		# once Jupyter recovers or comes back online.
		if self.cardiac_arrest_timeout:
			if self.last_heartbeat < (datetime.now() - self.cardiac_arrest_timeout):
				self.logger.warn('Cardiac arrest!')
				raise CardiacArrest


	def tear_down(self):
		"""
		Disassemble the kernel. Leaves it as an object that could, technically, re-launch.
		try:
			try:
				self._pre_tear_down()
				
				self.logger.info('Tearing down kernel %(kernel_id)s...' % self)
				
				self._stop_role('execution')
				self._stop_role('process')
				sleep((self.zpoll_timeout_ms/1000.0) *4)
	
				super(JupyterKernelCore, self).tear_down()
				
				if self.session:
					self.session.destroy()
				
			finally:
				self._post_tear_down()

		# make absolutely sure the zcontext is cleaned up
		finally:
			self.logger.debug('Tearing down ZContext...')
			if self.zcontext.isEmpty() and self.zcontext.isClosed():
				self.logger.warn('ZContext for already emptied and closed')
				return
			
			try:
				self.logger.debug('Closing pollers...')
				execution_zpoller = self.execution_zpoller
				self.execution_zpoller = None
				execution_zpoller.destroy()
				
				process_zpoller = self.process_zpoller
				self.process_zpoller = None
				process_zpoller.destroy()
				
				self.logger.debug('Destroying sockets...')
				for socket in self.zcontext.getSockets():
					self.zcontext.destroySocket(socket)
				
				for attr in [attr for attr in self.__slots__ if attr.endswith('_port') or attr.endswith('_socket')]:
					setattr(self, attr, None)
			finally:
				self.logger.debug('Destroying zcontext...')
				self.zcontext.destroy()
				sleep(1.5) # give everything a moment to settle, close, finallize, etc.
				self.logger.info('Done. Good-bye!')

		finally:
			# regardless of the success breaking down the kernel, 
			# run any user-defined post-tear down work
			self._post_tear_down()



	def launch_kernel(self):
		"""
		Bring the kernel online.

		"""
		
		# run any user-defined pre-launch methods
		self._pre_launch()
		
		if self.ACTIVE_HANDLER_RELOAD:
			self.reload_handlers()

		# initialize a zcontext that will handle all the ZMQ sockets, polling, and messages
		assert not self.is_launched, "ZContext already launched! HCF >_<"
		self.zcontext = ZContext()
		
		# create and bind the ZMQ sockets we'll be using
		for role in self._JUPYTER_ROLES:
			# create sockets
			socket = self.zcontext.createSocket(self.ZMQ_ROLE_SOCKET_TYPES[role])
			
			# configure for encryption
			socket.setCurveServer(True)
			socket.setCurvePublicKey(self._server_public_key)
			socket.setCurveSecretKey(self._server_secret_key)
			
			self[role + '_socket'] = socket
			
			# if not explicitly requested by kernel startup,
			# then bind each to a random port (a connection file may have been
			# provided that declared what ports to use, so use those if set)
			if self[role + '_port'] is None:
			   self[role + '_port'] = self.bind_random_port(self[role + '_socket'])
			else:
			   self.bind_selected_port(self[role + '_socket'], self[role + '_port'])
			self.logger.trace('%-16s on port %d' % (role, self[role + '_port']))
		
		# broadcast that the kernel is coming online now that we have sockets for it
		declare_starting(self)

		# control and heartbeat have a dedicated poller to ensure kernel can't be blocked
		self.process_zpoller = ZPoller(self.zcontext)
		for socket in self.process_sockets:
			self.process_zpoller.register(socket, ZPoller.POLLIN)

		# shell, iopub, and stdin are bundled for the actual remote code execution
		self.execution_zpoller = ZPoller(self.zcontext)
		for socket in self.execution_sockets:
			self.execution_zpoller.register(socket, ZPoller.POLLIN)

		# create an execution context for us to run code inside
		self.new_execution_session()

		# start the zmq socket polling
		# (but only if not already running)
		if 'process' not in self.active_roles:
			self.poll_process()
		if 'execution' not in self.active_roles:
			self.poll_execution()
			#self.start_execution_context()
		
		# give everything a moment to settle and come online
		sleep(0.25)
		
		# run any user-defined post-launch methods
		self._post_launch()
		
		# announce that startup is complete
		declare_idle(self)



	def new_execution_session(self):
		self.session = ExecutionContext(self)
		try: # signal to the kernel provisioner that a new session is made
			self.heartbeat_socket.send('restart')
		except:
			pass # maybe not set up yet


	@property
	def process_sockets(self):
		return [self[role + '_socket'] for role in self._PROCESS_ROLES]

	
	@property
	def execution_sockets(self):
		return [self[role + '_socket'] for role in self._EXECUTION_ROLES]


	def start_execution_context(self):
		if self._has_threads('execution'):
			self._stop_role('execution')
		self.poll_execution()


	def poll_execution_setup(self):
		"""Prepare for the process loop"""
		# create a new session inside this thread
		self.new_execution_session()

	@Context.poll('process')
	def poll_process(self):
		if self.interrupted or self.process_zpoller is None:
			return
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
		if self.interrupted or self.execution_zpoller is None:
			return
		with ZmqErrorCatcher(self) as catcher:
			self.execution_zpoller.poll(self.zpoll_timeout_ms)        
			for role, socket in zip(self._EXECUTION_ROLES, self.execution_sockets):
				if self.execution_zpoller.isReadable(socket):
					self._handle_zmessage(role, socket)


	def reload_handlers(self):
		"""Allow for dynamic patching of handlers even while a kernel is running."""
		for role in self._JUPYTER_ROLES:
			self[role + '_handler'] = reload_function(self[role + '_handler'])
	
	
	@property
	def now(self):
		# TODO: should include UTC tz object
		return datetime.utcnow().isoformat()[:23] + 'Z'
	
	
	@property
	def is_launched(self):
		"""If there's an active ZContext, we're live!"""
		return not (self.zcontext is None or self.zcontext.isClosed())
	
	@property
	def is_interrupted(self):
		# if the not interrupted, check the pulse and perhaps suggest it
		if not self.interrupted:
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
		"""
		Returned to the kernel provisioner for the kernel manager.
		Used by Jupyter to verify it's connection details were respected.
		"""
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
			
			'server_public_key': self._server_public_key,
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
	"""
	The Kernel.

	Connects the JupyterKernelCore to the Context methods.
	"""
	_INITIAL_LOGGING_LEVEL = DEFAULT_LOGGING_LEVEL
	_LOGGER_CLASS = Logger
	
	_CONTEXT_THREAD_ROLE = 'overwatch'
	
	_THREAD_NAME_SEPARATOR = ':' # avoid '-' because of UUID identifiers
	
	_EVENT_LOOP_DELAY = 0.01 # seconds
	_THREAD_DEATH_LOOP_WAIT = 0.1 # seconds


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
	"""A helper function to show how to launch a kernel."""
	if not kernel_init_kwargs:
		kernel_init_kwargs['kernel_id']= random_id()
	
	try:
		kernel = JupyterKernel(**kernel_init_kwargs)
		kernel.start_loop()
		return kernel
	except:
		exc_type, exc_val, exc_tb = sys.exc_info()
		logger.error(formatted_traceback(exc_val, exc_tb))
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