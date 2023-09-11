
from fnmatch import fnmatch as glob_match
import re

RE_FLAG_MAP = {
	'i': re.IGNORECASE,
	'l': re.LOCALE,
	'm': re.MULTILINE,
	's': re.DOTALL,
	'u': re.UNICODE,
	'x': re.VERBOSE,
}
# include upper case flagging
for flag in RE_FLAG_MAP:
	RE_FLAG_MAP[flag.upper()] = RE_FLAG_MAP[flag]

def pattern_match(pattern, string, re_flags=0):
	# regex starts and ends with a whack
	if pattern.startswith('/'):
		pattern, _, flags = pattern[1:].rpartition('/')
		return re.match(pattern, string, re_flags + sum(
			RE_FLAG_MAP[flag] for flag in flags
		)) is not None
	else:
		return glob_match(string, pattern)

def pattern_filter(pattern, iterable, re_flags=0):
	return [value 
			for value 
			in iterable 
			if pattern_match(pattern, value, re_flags)
		]


def _run_tests():
	from shared.tools.patterns import pattern_match, pattern_filter
	
	# glob example
	assert     pattern_match('*', 'asdf')
	assert     pattern_match('a*', 'asdf')
	assert not pattern_match('as[q]f', 'asdf')
	assert     pattern_match('a*[dr]*', 'asdf')
	
	# regex example
	assert     pattern_match('/asdf/', 'asdf')
	assert not pattern_match('/asdf/', 'ASDF')
	assert     pattern_match('/asdf/i', 'ASDF')
	assert     pattern_match('/.*/i', 'qwer')
	
	# iterable filtering
	test_list = ['asdf', 'ASDF', 'qwer','zxcv', '1qaz']
	assert pattern_filter('a*', test_list)      == ['asdf', 'ASDF']
	assert pattern_filter('*a*', test_list)     == ['asdf', 'ASDF', '1qaz']
	assert pattern_filter('/asdf/', test_list)  == ['asdf']
	assert pattern_filter('/asdf/i', test_list) == ['asdf', 'ASDF']
	
