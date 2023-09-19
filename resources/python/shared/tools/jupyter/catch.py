"""
	Error handling stuff goes here.
"""


logger = shared.tools.jupyter.logging.Logger()

from java.lang import Exception as JavaException
import java.nio.channels.ClosedSelectorException as JavaNioChannelsClosedSelectorException


from shared.tools.jupyter.zmq import ZMQException, ZError



__all__ = [
	'python_full_stack', 'java_full_stack', 'formatted_traceback',
	'JavaException', 'JavaNioChannelsClosedSelectorException',
	'ZMQException', 'ZError',
	
	'ZmqErrorCatcher',
]

# error utility
from shared.tools.error import *


class ZmqErrorCatcher(object):
	"""
	Handy context manager to wrap where ZMQ socket errors might be thrown.
	
	Catches and logs them.
	
	When ZMQ crashes and burns - say when the thread is interrupted - this will
	consume ZMQ panicing and sqelch the expected errors. This will only happen
	when the kernel context is tearing itself down (basically), so we'll be using
	zcontext.destroy anyhow, which is more thorough anyhow.
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
				# assume this is caught by the calling function
				#self.context.logger.error(formatted_traceback(exc_val, exc_tb))
				#raise exc_val
				pass # don't handle it, let it percolate up the stack
		except ZError as zmq_error:
			self.logger.error('ZMQ error %(zmq_error)r')
		except ZMQException as zmq_error:
			self.logger.error('ZMQ Handler error %(zmq_error)r')
		except JavaNioChannelsClosedSelectorException as channel_closed_error:
			return True # squelch
		except JavaException as java_interruption_sideeffect:
			if 'java.nio.channels.ClosedChannelException' in repr(java_interruption_sideeffect):
				return True # squelch # gawd just stop throwing this when murdered!
			else:
				raise java_interruption_sideeffect
		finally:
			self.context.interrupted = interrupt
