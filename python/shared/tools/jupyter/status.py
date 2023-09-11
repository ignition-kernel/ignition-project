"""
	
	NOTE: v5.0 all message indicate busy/idle, so only Kernel polling core will perform this
	
	https://jupyter-protocol.readthedocs.io/en/latest/messaging.html#kernel-status
"""
logger = shared.tools.jupyter.logging.Logger()


EXECUTION_STATES = set(('busy', 'idle', 'starting'))


__all__ = ['declare_busy', 'declare_idle']


def update_status(status, kernel, message=None):
	assert status in EXECUTION_STATES
	with kernel.iopub_broadcast('status', message) as update:
		update.content.execution_state = status


def declare_starting(kernel):
	update_status('starting', kernel)

def declare_busy(kernel, message=None):
	update_status('busy', kernel, message)
	
	if message and message.header.msg_type in kernel.traps.get('message_type', []):
		logger.trace('[%s] %r' % (message.header.msg_type, message.dump()))

def declare_idle(kernel, message=None):
	update_status('idle', kernel, message)


