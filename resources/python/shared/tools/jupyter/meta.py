"""
	Metadata for Jupyter

	Possibly deprecated, or at least not used yet.
	This is stuff that the protocol mentions it can use, but not obviously useful yet.
"""



from shared.tools.meta import getIgnitionContext
from shared.tools.net import default_ip



def get_gateway_hyperlink(endpoint='web/status/sys.overview', force_ssl=False):
	"""
	TODO: make this work for Designer sessions too.
	"""
	context = getIgnitionContext()
	
	webServerConfig = context.getWebResourceManager().getWebServerManager().getConfig()
	
	url_parts = {
		'endpoint': endpoint,
	}
	
	if force_ssl or webServerConfig.isForceSecureRedirect():
		url_parts['protocol'] = 'https'
		url_parts['port'] = webServerConfig.getHttpsPort()
	else:
		url_parts['protocol'] = 'http'
		url_parts['port'] = webServerConfig.getHttpPort()

	if webServerConfig.getPublicAddress():
		url_parts['address'] = webServerConfig.getPublicAddress()
	else:
		url_parts['address'] = default_ip()
	
	return '%(protocol)s://%(address)s:%(port)s/%(endpoint)s' % url_parts

