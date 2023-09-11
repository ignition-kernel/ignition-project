logger = shared.tools.jupyter.logging.Logger()

from shared.tools.jupyter.logging import log_message_event


@log_message_event
def comm_msg(kernel, message):
	logger.debug('comm message: %r' % (message.dump(),))
	kernel.comms[message.content.comm_id].update(message.content.data)


# TODO: handle this message we get on resets
#          content : <'dict'> of 2 elements
#                       comm_id : u'bf012122-fa30-484b-9a40-93825c06b0af'
#                          data : <'dict'> of 1 elements
#                                    method : u'request_states'
#           header : <'dict'> of 6 elements
#                           date : u'2023-07-12T03:43:48.149Z'            
#                         msg_id : u'cea7dae3-1039-4ce0-8907-0bba4eeebe28'
#                       msg_type : u'comm_msg'                            
#                        session : u'44382645-4504-4a30-9ac8-d8e073196308'
#                       username : u''                                    
#                        version : u'5.2'                                 
#         metadata : <'dict'> of 0 elements
#    parent_header : <'dict'> of 0 elements




@log_message_event
def comm_open(kernel, message):
	"""
	
	https://jupyter-protocol.readthedocs.io/en/latest/messaging.html#opening-a-comm
	"""
	kernel.open_comm(
		comm_id = message.content.comm_id,
		target_name = message.content.target_name,
		data = message.content.data,
	)


@log_message_event
def comm_close(kernel, message):
	"""
	
	https://jupyter-protocol.readthedocs.io/en/latest/messaging.html#tearing-down-comms
	"""
	kernel.close_comm(
		comm_id = message.content.comm_id,
		data = message.content.data,	
	)


@log_message_event
def comm_info_request(kernel, message):
	"""
	
	https://jupyter-protocol.readthedocs.io/en/latest/messaging.html#comm-info
	"""
	logger.trace('comm info request: %r' % (message.dump(),))
	
	
	target_name = message.content.target_name
	if target_name and not target_name in kernel.comm_targets:
		with kernel.shell_message('comm_close', message) as reply:
			reply.content.comm_id = message.content.comm_id
	else:
		with kernel.shell_message('comm_info_reply', message) as reply:
			if target_name:
				reply.content.comms = {
					comm.comm_id: {'target_name': comm.target_name}
					for comm
					in kernel.comm_targets[target_name]
				}
			else:
				reply.content.comms = {
					comm.comm_id: {'target_name': comm.target_name}
					for comm
					in kernel.comms.values()
				}	

@log_message_event
def comm_info_reply(kernel, message):
	"""
	
	https://jupyter-protocol.readthedocs.io/en/latest/messaging.html#comm-info
	"""
	raise NotImplementedError('Kernel does not yet request client comms')


COMMS_DISPATCH = {
	'comm_msg': comm_msg,
	'comm_open': comm_open,
	'comm_close': comm_close,
	'comm_info_request': comm_info_request,
	'comm_info_reply': comm_info_reply,
}