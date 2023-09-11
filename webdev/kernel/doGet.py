def doGet(request, session):
	
	from shared.tools.jupyter.catch import JavaException, formatted_traceback
	import sys
	
	try:
		result = shared.tools.jupyter.handlers.web.kernel.doGet(request)
		return {'json': result}

	except (Exception, JavaException) as error:
		exc_type, exc_val, exc_tb = sys.exc_info()
		shared.tools.logging.Logger().error(formatted_traceback(exc_val, exc_tb))
	
		response = request["servletResponse"]
		response.setStatus(404)

#		import sys
#		exception_type, exception, exception_traceback = sys.exc_info()
#		
#		if isinstance(exception, Exception):
#			import traceback
#			stacktrace = ''.join(
#				traceback.format_exception(exception_type, exception, exception_traceback)
#			)
#		elif isinstance(exception, JavaException):
#			stacktrace = java_full_stack(exception)
#		else:
#			stacktrace = repr(exception)
#		return {'response': stacktrace}

#	log = shared.tools.logging.Logger()
#	
#	from shared.tools.jupyter.core import KernelContext
#	
#	if request["remainingPath"]:
#		kernel_id = request["remainingPath"][1:]
#		try:
#			return {'json': KernelContext[kernel_id].connection_file}
#		except KeyError:
#			response = request["servletResponse"]
#			response.setStatus(404)
#			return
#	else:
#		return {'json': [kernel.kernel_id for kernel in KernelContext]}