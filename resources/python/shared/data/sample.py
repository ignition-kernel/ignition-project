"""
	Helper(s)/framework for gathering samples, usually over time

"""

import traceback


# For slightly faster comparisons, 
#   we'll transparently use Java's epoch millis instead of Python standard datetime
from java.lang.System import currentTimeMillis
# ... but still use timedelta to be standard
from datetime import datetime, timedelta


DEFAULT_SAMPLE_SECONDS = 0.100 # seconds


class TimedSampleFrame(object):
	__slots__ = [
		'duration', 'samples', '_complete',
		'_start', '_stop', 
		'_population_size', # optional metadata
	]
	
	def __init__(self, duration=DEFAULT_SAMPLE_SECONDS):
		if not isinstance(duration, timedelta):
			duration = timedelta(seconds=duration)
		self.duration = duration
		self.samples = None
		self._start = None
		self._stop = None
		
		self._population_size = None # only if known
		self._complete = False


	def gather_pool(self):
		raise NotImplementedError
	

	def now(self):
		return currentTimeMillis() # datetime.now()
	
	def start(self):
		assert self._start is None, "Sampling already in progress; sampling can only be started exactly once."
		self._start = self.now()
		self._stop = self._start + int(self.duration.total_seconds()*1000) # self._start + self.duration
	
	@property
	def finished(self):
		return self._start and self.now() > self._stop
	
	@property
	def fully_sampled(self):
		return self._complete
		
	@property
	def population_size(self):
		return self._population_size
	
	
	def __enter__(self):
		return self
	
	def __exit__(self, exc_type, exc_val, exc_tb):
		pass
	
	
	def __len__(self):
		return len(self.samples)
	
	def __iter__(self):
		if self.finished:
			population = self.samples
		else:
			population = self.collect_samples()
		 
		for sample in population:
			yield sample


	def collect_samples(self):
		self.start()
		sample_pool = self.gather_pool()
		
		samples = []
		try:
			while not self.finished:
				samples.append(next(sample_pool))
				yield samples[-1]
		except StopIteration:
			self._complete = True
			self._population_size = len(samples)
		except Exception as error:
			print traceback.format_exc()
			raise error
		finally:
			# lock down the results
			self.samples = tuple(samples)
		
