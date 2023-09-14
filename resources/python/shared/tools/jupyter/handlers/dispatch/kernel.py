logger = shared.tools.jupyter.logging.Logger()

from shared.tools.jupyter.logging import log_message_event
#from shared.tools.jupyter.meta import get_gateway_hyperlink



@log_message_event
def kernel_info_request(kernel, message):
	with kernel.shell_message('kernel_info_reply', message) as reply:
		reply.ids = message.ids
		reply.content = {
		    "protocol_version": "5.0",
	        "implementation": kernel.kernel_name,
	        "implementation_version": "1.1.2",
	        "language_info": {
	            "name": 'jython',
	            "version": "1.0",
	            'mimetype': "text/x-python2",
	            'file_extension': ".py",
	            'pygments_lexer': "python2", # https://pygments.org/docs/lexers/#pygments.lexers.python.Python2Lexer
	            'codemirror_mode': "Python", # https://codemirror.net/5/mode/python/index.html
	            'nbconvert_exporter': "",
	        },
	        "banner": "Metatools kernel - tools for building tools",
	        "help_links": [
#	        	{	# only gateway, does not apply to designer
#	        		'text': 'Gateway Status', 
#	        	 	'url' : get_gateway_hyperlink('web/status/sys.overview', force_ssl=True),
#	        	},
	        ]
		}


KERNEL_DISPATCH = {
	'kernel_info_request': kernel_info_request,
}
