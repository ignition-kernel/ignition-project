"""
	Run code!
	
	TODO: apply debug on an AST level using DAP
		https://microsoft.github.io/debug-adapter-protocol/

"""
logger = shared.tools.jupyter.logging.Logger()


import ast



from shared.tools.jupyter.catch import *


## OK this is actually substantial overkill, especially since we're handling our own history
#from shared.tools.debug.hijack import SysHijack, Thread
#class StandardHijack(SysHijack):
#	"""
#	Capture (and likely release) system info reliably.	
#	"""
#	def __init__(self):
#		thread = Thread.currentThread()
#		super(StandardHijack, self).__init__(thread)



from StringIO import StringIO



DEFAULT_DISPLAYHOOK = shared.tools.pretty.displayhook









class Executor(object):
	"""
	Capture the system st
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
		if obj is not None:
			self.display_objects.append(obj)
		if self.continuous_interactive:
			self.redirected_displayhook(obj)
	
	
	def execute(self, code):
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
		try:
			exec(self.code, self.global_context, self.local_context)
		except (Exception, JavaException) as error:
			self.last_error = sys.exc_info()

	def run_interactive(self):
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