"""
	Store the execution results for later reference.

	To gain many of the cool extra bits of introspective functionality
	that stuff like IPython can provide, execution is tracked and recorded.
	When an execution context session is created, In[] and Out[] are added,
	each of which are an instance of ResultHistory, wrapping the ExecutionContext
	attributes in a little bit of syntactic sugar.

	It also logs standard in/out/error. Objects sent to the displayhook, meaning
	that results of statements can also be retrieved from past executions.
	Of course, exceptions are also logged, making going back and checking past
	or erased stacktraces easier.
"""
logger = shared.tools.jupyter.logging.Logger()


from shared.tools.jupyter.catch import *



class ResultHistory(object):
	"""Helper class to disambiguate context history"""
	__slots__ = ['execution_context', 'target_attribute']
	def __init__(self, execution_context, target_attribute):
		self.execution_context = execution_context
		self.target_attribute = target_attribute
	
	def __getitem__(self, key):
		return getattr(self.execution_context[key], self.target_attribute)




class ExecutionResults(object):
	"""A simple struct to hold results"""
	__slots__ = [
		'_code', '_display_object', '_error',
		'_stdin', '_stdout', '_stderr', 
		'_notebook_cell_id',
	]
	
	def __init__(self, executor):
		assert executor.finished
		self._code = executor.code
		self._display_object = executor.display_object # keep only last, like normal IPython
		self._stdin  = executor.redirected_stdin.getvalue()
		self._stdout = executor.redirected_stdout.getvalue()
		self._stderr = executor.redirected_stderr.getvalue()
		self._error  = executor.last_error
		self._notebook_cell_id = executor.notebook_cell_id
	
	@property
	def code(self):
		return self._code
	
	@property
	def _(self):
		return self._display_object
	
	@property
	def display_object(self):
		return self._display_object
	
	@property
	def stdin(self):
		return self._stdin
	
	@property
	def stdout(self):
		return self._stdout

	@property
	def stderr(self):
		return self._stderr
	
	
	@property
	def error(self):
		return self._error or None
	
	@property
	def exception_type(self):
		return self._error[0] if self._error else None
	
	@property
	def exception(self):
		return self._error[1] if self._error else None
	
	@property
	def traceback(self):
		return self._error[2] if self._error else None
	
	@property
	def formatted_traceback(self):
		return formatted_traceback(self.exception, self.traceback)
	
	@property
	def notebook_cell_id(self):
		return self._notebook_cell_id
	
	def __str__(self):
		output = []
		if self.stdin:
			output += [
				'Input:',
			] + ['  ' + line for line in self.stdin.splitlines()]
		if self.stdout:
			output += [
				'Print:',
			] + ['  ' + line for line in self.stdout.splitlines()]
		if self.stderr:
			output += [
				'Error:',
			] + ['  ' + line for line in self.stderr.splitlines()]
		if self._:
			output += [prettify(self._)]
		return '\n'.join(output)
	
	def __repr__(self):
		return ' '.join([x for x in ['<',
			'ExecResult',
			'In'  if self.stdin  else '',
			'Out' if self.stdout else '',
			'ERR' if self.stderr else '',
			'Obj' if self._      else '',
		'>'] if x])


