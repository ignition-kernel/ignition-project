"""


"""
logger = shared.tools.jupyter.logging.Logger()

from shared.tools.jupyter.logging import log_message_event
from shared.tools.jupyter.handlers.dispatch.kernel import kernel_info_request



def message_handler(kernel, message):
	logger.trace('[Dispatch] [%s]' % (message.header.msg_type,))
	
	
	CONTROL_DISPATCH.get(
			message.header.msg_type, 
			not_implemented_message_type
		)(kernel, message)



@log_message_event
def shutdown_request(kernel, message):
	full_tear_down = not message.content.restart
	
	with kernel.control_message('shutdown_reply', message) as reply:
#		try:

#		except:
#			exc_type, exc_error, exc_tb = sys.exc_info()
#			reply.content ={
#				'status'   : 'error',
#				'ename'    : exc_type.__name__,
#				'evalue'   : exc_error.message,
#				'traceback': formatted_traceback(exc_error, exc_tb).splitlines(),
#			}
		if message.content.restart:
			kernel.new_execution_session()
		else:
			pass # we'll leave tearing down to Ignition
		
		reply.content.status = 'ok'
		
		reply.content.restart = message.content.restart

	if full_tear_down:
		kernel.tear_down()



@log_message_event
def interrupt_request(kernel, message):
	
	with kernel.control_message('interrupt_reply', message) as reply:
		# TODO: make this not a NOP :D :D :D
		reply.content.status = 'ok'





def not_implemented_message_type(kernel, message):
	logger.error("Unimplemented message type: %r" % (message.header.msg_type,))



CONTROL_DISPATCH = {
	'shutdown_request': shutdown_request,
	'interrupt_request': interrupt_request,
	
	'kernel_info_request': kernel_info_request,
}


