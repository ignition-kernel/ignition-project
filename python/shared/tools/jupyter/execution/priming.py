"""
	Basically just a place to put different priming contexts.
	
	Personally, I prefer my metatools stuff :) - ARG

	Note that there is a difference between locals and globals, but it's not quite obvious.
		If an execution context sets something as local, it will _not_ be available when compiled
		into a function's body since the function body overrides the locals. (Globals don't become
		local to a function without `global`, after all.)
	As a result, anything executed as though module-level or from the interactive prompt is treated
	as global. Any local changes clobber global scope in the execution context.	
	
"""

logger = shared.tools.jupyter.logging.Logger()

from shared.tools.jupyter.execution.results import ResultHistory



class ScopeMixin(object):
	
	
	def inject_scope_history(self):
		ec_locals  = self.python_state_locals
		
		# IPython-y things
		ec_locals['In'] = ResultHistory(self, 'code')
		ec_locals['Out'] = ResultHistory(self, 'display_object')
	
	def inject_scope_metatools(self):
		ec_locals  = self.python_state_locals
	
		# helpful interactive bits
		ec_locals['kernel'] = self.kernel
		ec_locals['context'] = shared.tools.meta.getIgnitionContext()
		ec_locals['p'] = shared.tools.pretty.p
		ec_locals['pdir'] = shared.tools.pretty.pdir

	def inject_scope_project(self, project_name):		
		ec_globals = self.python_state_globals
		
		ignition_context = shared.tools.meta.getIgnitionContext()
		
		try:
			# first assume gateway scoping
			project_manager = ignition_context.getProjectManager()
			script_manager = project_manager.getProjectScriptManager(project_name)
		except AttributeError:
			assert project_name == ignition_context.getProjectName()
			script_manager = ignition_context.getScriptManager()
		
		ec_globals.update(script_manager.createLocalsMap())


	def __init__(self, 
				 include_metatools=True,
				 include_project='jupyter',
				 *args, **kwargs):
		super(ScopeMixin, self).__init__(*args, **kwargs)
		
		if include_project:
			self.inject_scope_project(include_project)
		if include_metatools:
			self.inject_scope_metatools()
		self.inject_scope_history()
	
	