from shared.tools.pretty import p,pdir
from time import sleep
from shared.tools.thread import async, findThreads
from shared.tools.logging import Logger



def run_test(port=None):

	print [t.interrupt() for t in findThreads('echo-test')]
	
	
	@async(name='echo-test')
	def echo_test(port=None):
		
		
		from shared.tools.pretty import p,pdir
		from time import sleep
		from shared.tools.thread import async, findThreads
		from shared.tools.logging import Logger
	
		from shared.tools.jupyter.zmq import ZContext, ZMQ, SocketType
	
		try:
			zcontext = ZContext()
			
			socket = zcontext.createSocket(SocketType.REP)
			
			sleep(0.05)
			
			if port:
				socket.bind('tcp://127.0.0.1:%d' % port)
			else:
				port = socket.bindToRandomPort(
						'tcp://127.0.0.1', 
						30000,
						62000,
					)
	
			Logger().info('starting on port %d' % (port,))
			while True:
				payload = socket.recv(ZMQ.DONTWAIT)
				if payload:
					Logger().info('replying: %r' % (payload,))
					socket.send(payload)
				sleep(0.05)	
		
		finally:
			try:
				for socket in zcontext.getSockets():
					zcontext.destroySocket(socket)
			finally:
				zcontext.destroy()
	
	return echo_test(port)
	
