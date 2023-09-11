"""
	Execution history lookup
	
"""

logger = shared.tools.jupyter.logging.Logger()

from shared.tools.jupyter.logging import log_message_event

def history_request(kernel, message):
	raise NotImplementedError



#
#def history_request(kernel, message):
#	
#	
#	
#	
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#HISTORY_DISPATCH = {
#	'comm_msg': comm_msg,
#	'comm_open': comm_open,
#	'comm_close': comm_close,
#	'comm_info_request': comm_info_request,
#	'comm_info_reply': comm_info_reply,
#}