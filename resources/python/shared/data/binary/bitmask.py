
def bit_length(n): # return the bit size of a non-negative integer
    bits = 0
    while n >> bits: bits += 1
    return bits

def bit_string(bmo, length=0):
    return ''.join(str(bmo._mask >> i & 1) 
                   for i in range(length or bit_length(bmo._all_mask)))


class BitMaskOps(object):
    __slots__ = ('_mask', '_hash')

    def __init__(self, mask=0):
        self._mask = mask
        self._hash = self._calc_hash()

    # For comparisons, all inclusiveness is false if the comparitor is empty
    # (no saying ['a','b'] >= [] since that's uselessly and trivially true)
    def __ge__(self, obj):
        """self >= attr checks if self at least contains attr. Bitwise inclusion only"""
        return ((self._mask & obj._mask) == obj._mask)

    def __gt__(self, obj):
        """self > attr checks if self is a strict superset of attr. Bitwise inclusion AND check if greater"""
        return bool(obj) and ((self._mask & obj._mask) == obj._mask) and (self._mask > obj._mask)
    
    def __le__(self, obj):
        """self <= attr checks if attr at least contains self. Bitwise inclusion only"""
        return ((obj._mask & self._mask) == self._mask)
    
    def __lt__(self, obj):
        """self < attr checks if self is a strict subset of attr. Bitwise inclusion AND check if attr greater"""
        return bool(self) and ((obj._mask & self._mask) == self._mask) and (obj._mask > self._mask)
    
    
    def __or__(self, obj):
        return self.__class__(self._mask | obj._mask)

    def __and__(self, obj):
        return self.__class__(self._mask & obj._mask)

    def __xor__(self, obj):
        return self.__class__(self._mask ^ obj._mask)


    def __ior__(self, obj):
        self._mask |= obj._mask

    def __iand__(self, obj):
        self._mask &= obj._mask

    def __ixor__(self, obj):
        self._mask ^= obj._mask


    def __bool__(self):
        return self._mask != 0
    def __nonzero__(self):
        return self._mask != 0
    
    def _flag_state(self, ix):
        return bool(self._mask >> ix & 0x1)

    def __len__(self):
        return sum([1 & (self._mask >> i) for i in range(bit_length(self._mask))])
        # return bin(self._mask).count('1')
    
    
    def __lshift__(self, shiftNum):
        return self.__class__(self._mask << shiftNum)
    
    def __rshift__(self, shiftNum):
        return self.__class__(self._mask >> shiftNum)
    
    def __invert__(self):
        return self.__class__(self._mask ^ self._all_mask)


    # Technically how attributes should work. Makes mask manipulation easier.
    def __add__(self, obj):
        return self.__class__(self._mask | obj._mask)

    def __sub__(self, obj):
        return self.__class__(self._mask ^ (self._mask & obj._mask))


    def __iadd__(self, obj):
        self._mask |= obj._mask
    
    def __isub__(self, obj):
        self._mask ^= (self._mask & obj._mask)
    
        
    def __eq__(self, obj):
        if not isinstance(obj, BitMaskOps):
            return NotImplemented
        return self._mask == obj._mask
    
    def __ne__(self, obj):
        return self._mask == obj._mask
    
    @property
    def _bits(self):
        return (1<<ix for ix in range(bit_length(self._mask)) 
                if self._mask & 1<<ix)

    def __iter__(self):
        return self._bits

    def __repr__(self):
        return '<Mask %d>' % self._mask

    def _calc_hash(self):
        return hash((type(self), self._mask))

    def __hash__(self):
        return self._hash or self._calc_hash()


ZERO_MASK = BitMaskOps(0)
