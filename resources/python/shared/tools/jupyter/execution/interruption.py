"""
	Interrupt cell execution
	
	Safely stop without risk of racing and missing the mark.
	
	WIP: This is pretty 
"""
logger = shared.tools.jupyter.logging.Logger()


import functools
import sys
from time import sleep
from java.lang import Thread



def executing_juypter_code(frame=None):
	"""Returns true if the current execution stack is called from a Jupyter cell."""
	if frame is None:
		frame = sys._getframe()
	while frame:
		# ExecutionContext has this hardcoded
		if frame.f_code.co_filename.startswith('<Jupyter '):
			return True
		frame = frame.f_back
	return False


def interdict_and_interrupt(execution_context, timeout_ms=100):
	
	logger.warn('Interrupt requested! Checking... %r' % (Thread.currentThread(),))
	
	raise NotImplementedError('Remote interrupt not implemented. Kernel restart is required.')
#	return # NOP
	
	ec_sys = execution_context._context_sys
	
	# create the block that will hold execution
	# so long as this dict holds that value, it'll block
	block_signal = {'block': True}
	def continue_interdiction(signal=block_signal):
		return signal.get('block', None)
	
	interdictor = functools.partial(trace_interdictor, continue_interdiction, timeout_ms)
	
	try:
		logger.warn('installing interdiction on %r' % (ec_sys,))
		# e-brake execution to determine if it's safe to interrupt
		install_interdiction(ec_sys, interdictor)
	
		# check if interruption is needed now that execution has safely halted
		if not executing_juypter_code(ec_sys._getframe()):
			logger.info('Nothing to interrupt!')
			return

		# throw interrupt
		assert execution_context.thread is not Thread.currentThread(), 'Only external threads can request interdiction.'
		logger.warn('Interrupting: %r' % execution_context.thread)
#		execution_context.thread.interrupt()
		
		# release e-brake and allow execution to resolve the interrupt
		uninstall_interdiction(ec_sys)
		block_signal.clear()
		
	finally:
		# failsafe
		uninstall_interdiction(ec_sys)
		block_signal.clear()


def trace_interdictor(continue_interdiction, timeout_ms, *trace_args, **trace_kwargs):
	"""
	Intercept settrace, but only for a limited time.
	
	This is done in context of another thread impinging on this one's execution,
	so there's an assumption of this being a transient intercept.
	
	We'll depend on the context managers to complete the job of unwinding and signalling
	for clean up after release.	
	"""
	# burn down a fuse
	for fuse in reversed(range(timeout_ms)):
		if not continue_interdiction():
			# while this technically releases trace, note that 
			# we install across the stack to ensure interception occurs
			# even if the other thread's stack races us and moves on 
			# while we install the settrace, so this only releases one frame's.
			return None
		sleep(0.001) # sleep for 1 ms
	# fuse burned down!
	else:
		#crash the thread
		sys.exit()



def install_interdiction(sys_context, interdictor):
	"""
	Install the trace dispatcher to every level of the stack
	and then set the trace machinery in motion.
	
	Taken from metatools' debugger
	"""
	frame = sys_context._getframe()
	while frame:
		frame.f_trace = interdictor
		frame = frame.f_back

	# Trace is already initialized by this point, and setting
	#  the frame's trace ensures dispatch will trigger on the
	#  next line. That dispatch will call sys.settrace as well,
	#  but strictly from within the target thread.
	sys_context.settrace(interdictor)


def uninstall_interdiction(sys_context):
	"""Turn off trace and remove the trace dispatcher from every level
	in the stack.
	"""
	sys_context.settrace(None)

	frame = sys_context._getframe()
	while frame:
		# clear out any remnants of the previous trace attempt
		if frame.f_trace:
			del frame.f_trace
		frame = frame.f_back