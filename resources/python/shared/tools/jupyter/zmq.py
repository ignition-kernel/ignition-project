"""
	Juypter uses ZeroMQ for communications.
	
	For better native support, speed, and overhead, the kernel was built
	with JeroMQ in mind. The following will bootstrap in the expected
	classes if not a part of a module already.

"""

logger = shared.tools.jupyter.logging.Logger()


# splitting here for ease of copy/paste =/
__all__ = 'SocketType ZMQ ZMsg ZPoller ZContext ZMQException ZError Curve'.split()


from shared.tools.hotload import JarClassLoader

import os
import urllib2 # because it Just Works (TM) -- nothing clever, just data
import hashlib


# JAR_FOLDER = r'C:/Workspace/temp'
JAR_FOLDER = './user-lib/pylib'


JAR_FILENAME_PATTERN = '{library}-{major}.{minor}.{patch}.jar'

MAVEN_URL = (
	'https://repo1.maven.org/maven2/'
	+ '{project}/'
	+ '{major}.{minor}.{patch}/' 
	+ JAR_FILENAME_PATTERN
)


libraries = [
	dict(
		project='eu/neilalexander/jnacl',
		library='jnacl',
		version=(1,0,0),
		sha256_fingerprint='4ACCC9D2A56A6DD5198EC5E1C5C05A091DA563BCCD346FD6578EDC083152BEAA'
	),
	
	dict(
		project='org/zeromq/jeromq',
		library='jeromq',
		version=(0,5,3),
		sha256_fingerprint='A0973309AA2C3C6E1EA0D102ACD4A5BA61C8E38BAE0BA88C5AC5391AB88A8206'
	),

]



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



def load_jars(libraries, jar_folder=JAR_FOLDER):

	jar_file_paths = []
	
	for library in libraries:
		library_details = {
			'project': library['project'],
			'library': library['library'],
			'major': library['version'][0],
			'minor': library['version'][1],
			'patch': library['version'][2],
			}
		
		sha256_fingerprint = library['sha256_fingerprint']
		
		jar_filename = JAR_FILENAME_PATTERN.format(**library_details)
		expected_jar_location = os.path.abspath(os.path.join(jar_folder, jar_filename))
		
		if not os.path.exists(expected_jar_location):
			maven_url = MAVEN_URL.format(**library_details)
			logger.warn('{library} binary missing. Downloading from Maven at\n{maven_url}')
	
			with open(expected_jar_location, 'wb') as jar_file:
				## While I'd like to use system.net anything, I really don't know what this is binary blob is.
				## It definitely doesn't match the SHA256 and won't load and doesn't seem to be plaintext.
				# jar_data = system.net.httpGet(maven_url)
				jar_data = urllib2.urlopen(maven_url)
				jar_file.write(jar_data.read())
	
		validate_file_binary(expected_jar_location, sha256_fingerprint)
		
		jar_file_paths.append(expected_jar_location)

	_ = JarClassLoader(jar_file_paths)
#	if not expected_jar_location in sys.path:
#		_ = JarClassLoader(expected_jar_location)
#		sys.path.append(expected_jar_location)
	
	logger.debug('{library_names} added to path.', library_names=[l['library'] for l in libraries])

try:
	from org.zeromq import SocketType, ZMQ, ZMsg, ZPoller, ZContext, ZMQException
	from zmq import ZError
	from zmq.io.mechanism.curve import Curve

except ImportError:

	load_jars(libraries)

	from org.zeromq import SocketType, ZMQ, ZMsg, ZPoller, ZContext, ZMQException
	from zmq import ZError
	from zmq.io.mechanism.curve import Curve


