def doHead(request, session):
	log = shared.tools.logging.Logger()
	
	from shared.tools.jupyter.core import KernelContext
	
	assert request["remainingPath"][1:], "HEAD requires a kernel to poll."
	
	kernel_id = request["remainingPath"][1:]
	
	if kernel_id in KernelContext:
		return
	else:
		response = request["servletResponse"]
		response.setStatus(404)
		return