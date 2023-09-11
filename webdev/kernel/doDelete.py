def doDelete(request, session):
	
	from shared.tools.jupyter.catch import JavaException, formatted_traceback
	import sys
	
	try:
		result = shared.tools.jupyter.handlers.web.kernel.doDelete(request)
		return {'json': result}
	except (Exception, JavaException) as error:
		exc_type, exc_val, exc_tb = sys.exc_info()
		shared.tools.logging.Logger().error(formatted_traceback(exc_val, exc_tb))
		
		response = request["servletResponse"]
		response.setStatus(404)
		

#	log = shared.tools.logging.Logger()
#	
#	if request["remainingPath"]:
#		log.error('Request made to scram ' + request["remainingPath"])
#		
#		kernel_id = request["remainingPath"][1:]
#		
#		try:
#			shared.tools.jupyter.core.KernelContext[kernel_id].SCRAM()
#			return {'response': 'Kernel [%s] scrammed.' % (kernel_id,)}
#		except KeyError:
#			return {'response': 'FAILED: Kernel [%s] not found or already scrammed!' % (kernel_id,)}
#	
#	else:
#		log.error('Request made to scram all kernels')
#		scrammed_kernels = [kernel.kernel_id for kernel in shared.tools.jupyter.core.KernelContext]
#		shared.tools.jupyter.core.KernelContext.SCRAM_ALL()
#		
#		return {'json': {'scrammed': scrammed_kernels}}