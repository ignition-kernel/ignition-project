from shared.tools.pretty import p, pdir, install as install_pretty
from shared.tools.logging import Logger
Log = Logger
from shared.tools.thread import async, semaphore


from StringIO import StringIO

try:
	from shared.data.yaml.core import (
		dump as dumps_yaml, 
		load as load_yaml,
		)
	
	def loads_yaml(yaml_string, *args, **kwargs):
		return load_yaml(StringIO(yaml_string), *args, **kwargs)
		
	def dump_yaml(obj, file_pointer, *args, **kwargs):
		yaml_string = dumps_yaml(obj, *args, **kwargs)
		file_pointer.write(yaml_string)
		return yaml_string
except ImportError:
	pass # skip

try:
	from shared.data.toml._init import (
		load as load_toml, 
		loads as loads_toml, 
		dump as dump_toml, 
		dumps as dumps_toml,
		)
except ImportError:
	pass