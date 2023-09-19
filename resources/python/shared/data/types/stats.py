



from shared.data.stats import histogram, simple_histogram_plot, combine_descriptions



from shared.data.types.dictslots import DictSlotsMixin
from shared.data.types.mixins import ImmutableDictMixin

from itertools import izip_longest


def chain_attribute(dict_like, key_path, default=None):
	cursor = dict_like
	try:
		for key in key_path.split('.'):
			cursor = cursor[key]
	except KeyError:
		return default
	return cursor


class ImmutableOverridableDictSlots(ImmutableDictMixin, DictSlotsMixin):
	_slot_alias = {}
	
	def __init__(self, *slot_values, **overrides):
		for slot, value in izip_longest(self.__slots__, slot_values, fillvalue=None):
			setattr(self, slot, 
				chain_attribute(
					overrides, 
					self._slot_alias.get(slot, slot),
					default=value)
			)



class DisplayRoundedMixin:
	_roundable_properties = []

	def display_rounded(self):
		return {
			key: round(value, 3) if isinstance(value, float) else value
			for key, value 
			in self.items() + tuple( 
					(prop, self[prop]) 
					for prop 
					in self._roundable_properties
				)
			if isinstance(value, (int, long, float))
		}








class Histogram(DisplayRoundedMixin, ImmutableOverridableDictSlots):
	__slots__ = tuple(slot.strip() for slot
		in """
			start stop step
			outliers
			counts
		""".split())
	
	_roundable_properties = ['buckets']
		
	def __init__(self, data=None, counts=tuple(), outliers=0,
				 buckets=None, start=None, stop=None, step=None):
		if data and not counts:
			bounds, counts = histogram(data, buckets=buckets, start=start, stop=stop, step=step)
			outliers = len(data) - sum(counts)
		else:
			bounds = slice(start, stop, step)
		start = bounds.start
		stop  = bounds.stop
		step  = bounds.step
		
		
		super(Histogram, self).__init__(start, stop, step, outliers, counts)
		
	@property
	def buckets(self):
		return len(self.counts)
	
	@property
	def config(self):
		return slice(self.start, self.stop, self.step)
	
	def simple_plot(self, height=5):
		return simple_histogram_plot(self.config, self.counts, height)
	
	def __repr__(self):
		return '<Histogram [%(start)r: %(stop)r: %(step)r] %(outliers)d out (of %(buckets)d)>' % (
			self.display_rounded()
		)





class StatisticalDescription(DisplayRoundedMixin, ImmutableOverridableDictSlots):
	__slots__ = tuple(slot.strip() for slot
		in """
			n mean 
			min max span
			variance stddev
			sum 
		""".split())
	
	_slot_alias = {
		'stddev':   'standard deviation',
	}
	
	def __add__(self, another_description):
		return StatisticalDescription(
				**combine_descriptions(self, another_description)
			)
	

	def __repr__(self):
		return '<Stats |%(n)rn| %(mean)rμ ± %(stddev)rσ  [%(min)r: %(max)r]>' % (
			self.display_rounded()
		)





def _run_tests():
	data = [
		81.24,
		80.62,
		80.13,
		81.62,
		80.13,
		80.37,
		81.23,
		80.59,82.66,
		80.89,82.64,
		80.10,82.39,
		81.29,81.77,
		81.58,81.76,
		80.45,81.84,
		33.94,79.95,80.22,82.55,
		33.46,79.24,80.55,82.45,
		34.50,78.46,80.28,82.00,
		33.42,79.25,80.86,81.72,
		31.98,34.86,77.58,79.81,81.10,81.96,
		32.01,34.48,77.98,78.89,81.13,81.79,
		33.20,34.23,76.96,79.67,80.18,82.90,
		32.03,34.68,76.77,79.71,80.54,83.02,
		31.79,34.82,76.83,79.88,81.25,82.33,
		32.16,34.07,50.37,78.18,78.63,80.57,82.32,
		32.83,33.46,37.53,51.20,77.70,79.18,81.27,81.84,84.08,
		30.58,33.25,34.23,37.81,51.21,77.63,78.78,80.65,82.20,83.95,
		30.31,32.43,34.95,37.22,38.74,51.60,76.02,76.82,79.68,80.40,82.18,84.75,
		20.42,31.49,32.90,34.84,35.23,37.04,38.65,41.28,43.24,44.40,50.18,70.40,75.99,77.09,78.64,80.54,82.29,83.87,
		20.55,22.12,24.99,29.76,30.49,32.23,34.15,36.21,37.52,38.86,40.33,41.74,43.79,51.47,54.50,56.30,57.09,59.27,60.39,69.78,70.89,72.23,74.53,75.63,78.32,78.95,80.60,82.21,84.33,
		]
		
		
	assert '\n' + Histogram(data, buckets=39).simple_plot() == """
   28                                      +  
                                           ++ 
 Δ5.6          +                          +++ 
              ++         +               ++++ 
    0  +++  ++++++++++   + +++++    ++++++++++
-----  =======================================
 20.0  Δ1.6667                                85.0"""
