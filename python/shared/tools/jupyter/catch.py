logger = shared.tools.jupyter.logging.Logger()

from java.lang import Exception as JavaException
import java.nio.channels.ClosedSelectorException as JavaNioChannelsClosedSelectorException
from org.apache.commons.lang3.exception import ExceptionUtils
from org.apache.commons.lang3 import SystemUtils
import traceback


from shared.tools.jupyter.zmq import ZMQException, ZError



__all__ = [
	'python_full_stack', 'java_full_stack', 'formatted_traceback',
	'JavaException', 'JavaNioChannelsClosedSelectorException',
	'ZMQException', 'ZError',
	
	'ZmqErrorCatcher',
]

# error utility

def python_full_stack():
    import traceback, sys
    exc = sys.exc_info()[0]
    stack = traceback.extract_stack()[:-1]  # last one would be full_stack()
    if exc is not None:  # i.e. an exception is present
        del stack[-1]       # remove call of full_stack, the printed exception
                            # will contain the caught exception caller instead
    trc = 'Traceback (most recent call last):\n'
    stackstr = trc + ''.join(traceback.format_list(stack))
    if exc is not None:
         stackstr += '  ' + traceback.format_exc().lstrip(trc)
    return stackstr

def java_full_stack(error):
	return ExceptionUtils.getStackTrace(error)
	
	
def formatted_traceback(exception, exc_tb=None):
	if exception is None:
		return ''
	if isinstance(exception, Exception): # use the output of sys.exc_info()
		return ''.join(traceback.format_exception(type(exception), exception, exc_tb))
	elif isinstance(exception, JavaException):
		return java_full_stack(exception)
	else:
		return repr(exception)


class ZmqErrorCatcher(object):
	"""
	Handy context manager to wrap where ZMQ socket errors might be thrown.
	
	Catches and logs them.	
	"""
	
	def __init__(self, context):
		self.context = context

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		interrupt = True
		try:
			if exc_type is None:
				interrupt = False
			else:
				raise exc_val
		except ZError as zmq_error:
			self.logger.error('ZMQ error %(zmq_error)r')
		except ZMQException as zmq_error:
			self.logger.error('ZMQ Handler error %(zmq_error)r')
		except JavaNioChannelsClosedSelectorException as channel_closed_error:
			pass
		except JavaException as java_interruption_sideeffect:
			if 'java.nio.channels.ClosedChannelException' in repr(java_interruption_sideeffect):
				pass # gawd just stop throwing this when murdered!
			else:
				raise java_interruption_sideeffect
		finally:
			self.context.interrupted = interrupt