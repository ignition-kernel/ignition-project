"""
	Execution history lookup
	
	TODO: history lookup.

	Note that the IPython-style In[x] and Out[x] variables are available,
	so there's not a very strong need for this yet. Add that kernel.session
	has a full record of everything it has run, and this is a low priority
	feature.
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