"""
	Custom messages - comms
	
	https://jupyter-client.readthedocs.io/en/latest/messaging.html#custom-messages
"""
logger = shared.tools.jupyter.logging.Logger()


from shared.tools.jupyter.base import JupyterKernelBaseMixin



class KernelCommMixin(JupyterKernelBaseMixin):
	__slots__ = (
		# custom message management
		'comms', 'comm_targets',
		)
	
	def initialize_kernel(self, **init_kwargs):
		# ready for comms
		self.comms = {}
		self.comm_targets = {}
		
		super(KernelCommMixin, self).initialize_kernel(**init_kwargs)



	def open_comm(self, comm_id, target_name, data):
		if comm_id not in self.comms:
			comm = Comm(comm_id, target_name, data)
			self.comms[comm_id] = comm
			if not target_name in self.comm_targets:
				self.comm_targets[target_name] = []
			self.comm_targets[target_name].append(comm)

	def close_comm(self, comm_id):
		# already removed?
		if not comm_id in self.comms:
			return
		comm = self.comms[comm_id]
		target_name = comm.target_name
		try:
			self.comm_targets[target_name].remove(comm)
		except ValueError:
			pass # already removed
		if not self.comm_targets[target_name]:
			del self.comm_targets[target_name]
		del self.comms[comm_id]


class Comm(object):
	
	def __init__(self, kernel, comm_id, target_name, data=None):
		self.comm_id = comm_id
		self.target_name = target_name
		self.data = data or {}


	def update(self, data):
		logger.debug('Data added to %(self)r: %(data)r')
		self.data = data
	
	def __repr__(self):
				return '<Comm [%s] %s>' % (self.comm_id, self.target_name)