"""
	Juypter uses ZeroMQ for communications.
	
	For better native support, speed, and overhead, the kernel was built
	with JeroMQ in mind. The following will bootstrap in the expected
	classes if not a part of a module already.

"""

logger = shared.tools.jupyter.logging.Logger()


# splitting here for ease of copy/paste =/
__all__ = 'SocketType ZMQ ZMsg ZPoller ZContext ZMQException ZError'.split()


import os
import urllib2 # because it Just Works (TM) -- nothing clever, just data


JEROMQ_VERSION = {
	'major': 0,
	'minor': 5,
	'patch': 3
}
_SHA256_FINGERPRINT = 'A0973309AA2C3C6E1EA0D102ACD4A5BA61C8E38BAE0BA88C5AC5391AB88A8206'

JEROMQ_JAR = 'jeromq-%(major)d.%(minor)d.%(patch)d.jar' % JEROMQ_VERSION
JEROMQ_JAR_FOLDER = r'./user-lib/pylib'

MAVEN_URL = (
	'https://repo1.maven.org/maven2/org/zeromq/jeromq/'
	'%(major)d.%(minor)d.%(patch)d/jeromq-%(major)d.%(minor)d.%(patch)d.jar' % JEROMQ_VERSION
)


def validate_file_binary(location, signature):
	# validate binary
	import hashlib
	hash_chunk_size= 65536
	jar_sha256 = hashlib.sha256()
	with open(location, 'rb') as jar_file:
		while True:
			_data_chunk = jar_file.read(hash_chunk_size)
			if not _data_chunk:
				break
			jar_sha256.update(_data_chunk)
	assert jar_sha256.hexdigest().upper() == signature.upper(), 'SHA256 signature mismatch for %r' % (location,)


# Attempt to hotload
try:
	from org.zeromq import SocketType, ZMQ, ZMsg, ZPoller, ZContext, ZMQException
	from zmq import ZError
	logger.info('JeroMQ successfully loaded!')

# if not yet horked into the local classloader's scope, hoist it here
except ImportError:
	_expected_jar_location = os.path.abspath(os.path.join(JEROMQ_JAR_FOLDER, JEROMQ_JAR))
	
	if not os.path.exists(_expected_jar_location):
		logger.warn('JeroMQ binary missing. Downloading from Maven at %r' % (MAVEN_URL,))
		
		with open(_expected_jar_location, 'wb') as jar_file:
			## While I'd like to use system.net anything, I really don't know what this is binary blob is.
			## It definitely doesn't match the SHA256 and won't load and doesn't seem to be plaintext.
			# jar_data = system.net.httpGet(MAVEN_URL)
			jar_data = urllib2.urlopen(MAVEN_URL)
			jar_file.write(jar_data.read())
		
	try:
		validate_file_binary(_expected_jar_location, _SHA256_FINGERPRINT)
		
		logger.debug('JeroMQ not yet loaded. Hotloading from %r.' % (_expected_jar_location,))
		
		from shared.tools.hotload import jar_class_grind
		
		jar_class_grind([
			_expected_jar_location,
		])
		
		from org.zeromq import SocketType, ZMQ, ZMsg, ZPoller, ZContext, ZMQException
		from zmq import ZError
	
		logger.info('JeroMQ hotloaded from %r.' % (_expected_jar_location,))

	except AssertionError:
		raise ImportError('JeroMQ jar not as expected. Check version and file SHA256 signature!')