
from shared.tools.jupyter.catch import *
from shared.tools.jupyter.zmq import *
from shared.tools.thread import async, Thread

from time import sleep




@async(name="Jupyter-Kernel-XXXX-Listener")
def loopback_listener(kernel, identity=None, polling_ms_timeout=10):
	log = shared.tools.logging.Logger('Jupyter-Kernel', prefix='[%(kernel_id)s 0>_<0] ' % kernel)
	
	Thread.currentThread().setName('Jupyter-Kernel-%(kernel_id)s-Listener' % kernel)
	
	log.info('Loopback listener started')
	
	ZMQ_ROLE_SOCKET_TYPES = {
		'shell'    : SocketType.DEALER, #SocketType.ROUTER,
		'iopub'    : SocketType.SUB,    # SocketType.PUB,
		'stdin'    : SocketType.DEALER, # SocketType.ROUTER,
		'control'  : SocketType.DEALER, # SocketType.ROUTER,
		'heartbeat': SocketType.REQ,    # SocketType.REP,
	}
	roles = tuple(kernel._canonical_roles) # for ordering/consistency
	
	overwatch_thread = kernel.overwatch_thread
	
	try:
		zcontext = ZContext()
		
		sleep(0.5)
		
		sockets = dict(
			(role, zcontext.createSocket(socketType))
			for role, socketType
			in ZMQ_ROLE_SOCKET_TYPES.items()
		)
		
		if identity:
			log.debug('Setting listener as %s' % (identity,))
		
		for role, socket in sockets.items():
			if identity:
				assert socket.setIdentity(identity)
			socket.connect(('%%(transport)s://%%(ip)s:%%(%s_port)d' % role) % kernel)
		
		zpoller = ZPoller(zcontext)
		
		for role in roles:
			zpoller.register(sockets[role], ZPoller.POLLIN)
		
		sleep(0.1)
		
		log.info('Listening for kernel traffic...')
		
		# main loop - exit when kernel is stopped
		while overwatch_thread.getState() != Thread.State.TERMINATED:
			
			try:
				zpoller.poll(polling_ms_timeout)
				
				for role, socket in sockets.items():			
					if zpoller.isReadable(socket):
						if role == 'heartbeat':
							payload = socket.recv()
							log.info('[%s] %r' % (role, payload))
						else:
							zMessage = ZMsg.recvMsg(socket, ZMQ.DONTWAIT)
							if zMessage is not None:
								log.info('[%s] %r' % (role, zMessage))
								zMessage.destroy()
							else:
								log.info('[%s] %r' % (role, 'Message not complete or unread???'))
			
			except KeyboardInterrupt:
				log.error('Kernel interrupted')
			except Exception as python_interruption_sideeffect:
				log.error('Python Handler error %(python_interruption_sideeffect)r')
				log.error(python_full_stack())
			except (ZMQException, ZError) as zmq_error:
				log.error('ZMQ error %(zmq_error)r')
			except JavaNioChannelsClosedSelectorException as channel_closed_error:
				pass
				self.interrupted = True
			except JavaException as java_interruption_sideeffect:
				log.error('Java Handler error %(java_interruption_sideeffect)r')
				log.error(java_full_stack(java_interruption_sideeffect))

	finally:
		try:
			for socket in zcontext.getSockets():
				zcontext.destroySocket(socket)
		except ZMQException:
			pass
		else:
			zcontext.destroy()
	
	log.info('Loopback listener stopped')

