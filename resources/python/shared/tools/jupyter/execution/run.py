"""
	Run code!
	
	TODO: apply debug on an AST level using DAP
		https://microsoft.github.io/debug-adapter-protocol/

	Note that this operates in a vaguely similar style to how the metatools pdb
	implementation does SysHijack, intercepting the sys I/O hooks. Its use of
	context management as well as operating in its own thread isolates these
	shenanigans safely, though. It's reversible with more than enough layers of
	safety to keep it in line.
"""
logger = shared.tools.jupyter.logging.Logger()


from shared.tools.jupyter.catch import *
import ast


from shared.tools.jupyter.catch import *

from StringIO import StringIO



DEFAULT_DISPLAYHOOK = shared.tools.pretty.displayhook



class Executor(object):
	"""
	Run code in a controlled, logged way.

	An Executor wraps all the mechanics of running a chunk of code as well
	as logging output as it runs (if any) and the resulting object(s) hooked
	(if any). It also acts as the session information for the Python execution 
	context, allowing for past commands (and their results, if any) to be retrieved.
	"""
	__slots__ = [
		'captured_sys',
		'redirected_stdout', 
		'redirected_stdin', 
		'redirected_stderr',
		'redirected_displayhook',
		
		'code', 'local_context', 'global_context',
		'display_objects',
		'last_error',
		
		'interactive', 'continuous_interactive',
		'filename',
		'notebook_cell_id',
		
		'_installed', '_done',
		
		'original_stdin',
		'original_stdout',
		'original_stderr',
		'original_displayhook',
	]

	DEFAULT_FILENAME = '<interactive input>'

	def __init__(self, captured_sys, global_context, local_context, 
				 interactive=True, continuous_interactive=False,
				 displayhook=None, execution_location=None,
				 notebook_cell_id=None, # cell that requested execution
				 ):
		self.captured_sys = captured_sys
		self.local_context = local_context
		self.global_context = global_context
		
		self.code = None
		self.display_objects = []
		self.last_error = None
		
		self.filename = execution_location or self.DEFAULT_FILENAME
		self.interactive = interactive
		self.continuous_interactive = continuous_interactive
		
		self._installed = False
		self._done = False
		
		self.original_stdin       = None
		self.original_stdout      = None
		self.original_stderr      = None
		self.original_displayhook = None
		
		self.redirected_stdin  = StringIO()
		self.redirected_stdout = StringIO()
		self.redirected_stderr = StringIO()
		self.redirected_displayhook = displayhook or DEFAULT_DISPLAYHOOK
		
		self.notebook_cell_id = notebook_cell_id
	
	
	def isolated_displayhook(self, obj):
		"""
		Because Ignition is vaguely nonstandard in how the displayhook acts, 
		this isolates and replicates that effect.
		"""
		if obj is not None:
			self.display_objects.append(obj)
		if self.continuous_interactive:
			self.redirected_displayhook(obj)
	
	
	def execute(self, code):
		"""
		Run code.
		"""
		assert self.installed, 'Execution should be done only when context is managed.'
		assert self.code is None, 'Executor should not be used more than once'
		self.code = code
		try:
			if self.interactive:
				self.run_interactive()
			else:
				self.run_script()
		finally:
			self._done = True
	
	def run_script(self):
		"""
		Run the code as a monolithic block.
		"""
		try:
			exec(self.code, self.global_context, self.local_context)
		except (Exception, JavaException) as error:
			self.last_error = sys.exc_info()

	def run_interactive(self):
		"""
		Run the code as though it was entered in an interactive prompt.

		This is how most scripts seem to function in Ignition. It means that
		statements will displayhook values intermittently and not just at the
		end of the execution. 

		So if multiple functions were to return an object, but they have no variable
		to sink them into, then those objects to to the displayhook, and multiple
		entries would show up in StdOut.

		To replicate this effect, we'll ram the code through the ast parser, first.
		This lets us execute code on a statement-by-statement basis, logging as each 
		generate results (or not). It's not actually terrible since Python would do
		most of that anyhow, we're just interrupting the process a smidge. -ish.
		"""
		try:
			ast_tree = ast.parse(self.code)
		except Exception as error:
			self.last_error = sys.exc_info()
			return
		
		for node in ast_tree.body:
			statement = ast.Module()
			statement.body.append(node)
			
			try:
				statement_code = compile(statement, filename=self.filename, mode='single')
			except Exception as error:
				self.last_error = sys.exc_info()
				return
			
			try:
				if isinstance(statement, ast.Expr):
					result = eval(statement_code, self.global_context, self.local_context)
					self.isolated_displayhook(result)
				else:
					exec(statement_code, self.global_context, self.local_context)
				
				# clobber global given locals so imports and such carry into function scopes
				if isinstance(statement, ast.Module):
					self._sync_local_changes_onto_global()
				
			except KeyboardInterrupt as error:
				self.last_error = sys.exc_info()
			except (Exception, JavaException) as error:
				self.last_error = sys.exc_info()
				break # stop processing nodes
	
	def _sync_local_changes_onto_global(self):
		"""
		From the ExecutionContext module:
			Note that there is a difference between locals and globals, but it's not quite obvious.
				If an execution context sets something as local, it will _not_ be available when compiled
				into a function's body since the function body overrides the locals. (Globals don't become
				local to a function without `global`, after all.)
			As a result, anything executed as though module-level or from the interactive prompt is treated
			as global. Any local changes clobber global scope in the execution context.	
		"""
		self.global_context.update(self.local_context)
		self.local_context = {}
		
	
	@property
	def display_object(self):
		if self.display_objects:
			return self.display_objects[-1]
		else:
			return None
	
	@property
	def installed(self):
		"""Property to identify if this is actively intercepting sys I/O hooks."""
		return self._installed
	
	@property
	def finished(self):
		return self._done and not self._installed
	
	
	def install(self):
		# snapshot for later recovery
		self.original_stdin       = self.captured_sys.stdin
		self.original_stdout      = self.captured_sys.stdout
		self.original_stderr      = self.captured_sys.stderr
		self.original_displayhook = self.captured_sys.displayhook
		
		self.captured_sys.stdin       = self.redirected_stdin
		self.captured_sys.stdout      = self.redirected_stdout
		self.captured_sys.stderr      = self.redirected_stderr
		self.captured_sys.displayhook = self.isolated_displayhook
		
		self._installed = True
	
	
	def uninstall(self):
		self.captured_sys.stdin       = self.original_stdin
		self.captured_sys.stdout      = self.original_stdout
		self.captured_sys.stderr      = self.original_stderr
		self.captured_sys.displayhook = self.original_displayhook
		
		self._installed = False
	
	def __enter__(self):
		self.install()
		return self
	
	def __exit__(self, exc_type, exc_val, exc_tb):
		self.uninstall()

	def __del__(self):
		"""NOTE: This is NOT guaranteed to run, but it's a mild safeguard."""
		self.uninstall()





#==================================
#  Execution interrupt mechanics
#==================================


import functools


def interdict_and_interrupt(kernel, timeout_ms=100):
	execution_context = kernel.session
	ec_sys = execution_context.captured_sys
	
	# create the block that will hold execution
	# so long as this dict holds that value, it'll block
	block_signal = {'block': True}
	def continue_interdiction(signal=block_signal):
		return signal.get('block', None)
	
	interdictor = functools.partial(trace_interdictor, continue_interdiction, timeout_ms)
	
	try:
		# e-brake execution to determine if it's safe to interrupt
		install_interdiction(ec_sys, interdictor)
	
		# check if interruption is needed now that execution has safely halted
		
		
		
		
		# throw interrupt
		assert execution_context.thread is not Thread.currentThread(), 'Only external threads can request interdiction.'
		execution_context.thread.interrupt()
		
		# release e-brake and allow execution to resolve the interrupt
		uninstall_interdiction(ec_sys)
		block_signal.clear()
		
	finally:
		# failsafe
		uninstall_interdiction(ec_sys)
		block_signal.clear()


def trace_interdictor(continue_interdiction, timeout_ms, *trace_args, **trace_kwargs):
	"""
	Intercept settrace, but only for a limited time.
	
	This is done in context of another thread impinging on this one's execution,
	so there's an assumption of this being a transient intercept.
	
	We'll depend on the context managers to complete the job of unwinding and signalling
	for clean up after release.	
	"""
	# burn down a fuse
	for fuse in reversed(range(timeout_ms)):
		if not continue_interdiction():
			# while this technically releases trace, note that 
			# we install across the stack to ensure interception occurs
			# even if the other thread's stack races us and moves on 
			# while we install the settrace, so this only releases one frame's.
			return None
		sleep(0.001) # sleep for 1 ms
	# fuse burned down!
	else:
		#crash the thread
		sys.exit()



def install_interdiction(sys_context, interdictor):
	"""
	Install the trace dispatcher to every level of the stack
	and then set the trace machinery in motion.
	
	Taken from metatools' debugger
	"""
	frame = sys_context._getframe()
	while frame:
		frame.f_trace = interdictor
		frame = frame.f_back

	# Trace is already initialized by this point, and setting
	#  the frame's trace ensures dispatch will trigger on the
	#  next line. That dispatch will call sys.settrace as well,
	#  but strictly from within the target thread.
	sys_context.settrace(interdictor)


def uninstall_interdiction(sys_context):
	"""Turn off trace and remove the trace dispatcher from every level
	in the stack.
	"""
	sys_context.settrace(None)

	frame = sys_context._getframe()
	while frame:
		# clear out any remnants of the previous trace attempt
		if frame.f_trace:
			del frame.f_trace
		frame = frame.f_back






