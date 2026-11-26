from collections import deque as _deque


class Deque:
	def __init__(self, values=()):
		self._items = _deque(values)
		self._head = 1

	def push(self, value):
		self._items.append(value)

	def push_front(self, value):
		self._items.appendleft(value)
		self._head -= 1

	def pop(self):
		value = self._items.popleft()
		self._head += 1
		return value

	def pop_back(self):
		return self._items.pop()

	def peek(self):
		return self._items[0]

	def peek_back(self):
		return self._items[-1]

	def size(self):
		return len(self._items)

	def is_empty(self):
		return not self._items

	def push_queue(self, source):
		if source is self:
			raise ValueError("Cannot transfer a deque into itself")
		while not source.is_empty():
			Deque.push(self, source.pop())

	def push_front_queue(self, source):
		if source is self:
			raise ValueError("Cannot transfer a deque into itself")
		while not source.is_empty():
			Deque.push_front(self, source.pop())

	def pop_queue(self):
		result = Deque(self._items)
		self._head += len(self._items)
		self._items.clear()
		return result

	def pop_back_queue(self):
		result = Deque(reversed(self._items))
		self._items.clear()
		return result

	def peek_queue(self):
		return self

	def to_array(self):
		return list(self._items)

	def copy(self):
		result = Deque(self._items)
		result._head = self._head
		return result

	def copy_reverse(self):
		return Deque(reversed(self._items))

	def __len__(self):
		return len(self._items)

	def __iter__(self):
		return iter(self._items)


class _Unavailable:
	def __get__(self, instance, owner):
		raise AttributeError(f"{owner.__name__} does not expose this deque operation")


class _Restricted:
	push_front = _Unavailable()
	pop_back = _Unavailable()
	peek_back = _Unavailable()
	push_queue = _Unavailable()
	push_front_queue = _Unavailable()
	pop_queue = _Unavailable()
	pop_back_queue = _Unavailable()
	peek_queue = _Unavailable()
	to_array = _Unavailable()
	copy = _Unavailable()
	copy_reverse = _Unavailable()


class Queue(_Restricted, Deque):
	pass


class Stack(_Restricted, Deque):
	def push(self, value):
		Deque.push_front(self, value)


class pQue(Deque):
	def __init__(self, cmd="", cond="", bCond=False):
		super().__init__()
		self.pc = self._head - 1
		self.cmd = cmd
		self.cond = cond
		self.bCond = bCond
		self.skip = False

	def pc_index(self):
		return max(self._head - 1, min(self.pc, self._head + len(self._items)))

	def is_parked(self):
		return self.pc < self._head

	def release(self):
		self.pc = self._head
		return True

	def is_start(self):
		return self.pc == self._head

	def is_done(self):
		return self.pc >= self._head + len(self._items)

	def set_done(self):
		self.pc = self._head + len(self._items)
		return True

	def restart(self):
		return self.release()

	def increment_pc(self):
		end = self._head + len(self._items)
		if self.pc < end:
			self.pc += 1
		self.pc = max(self.pc, self._head)
		return self.pc < end

	def pc_item(self):
		if self.is_parked() or self.is_done():
			raise IndexError("Program counter is parked or past the end")
		value = self._items[self.pc - self._head]
		self.increment_pc()
		return value

	def set_cmd(self, cmd):
		self.cmd = cmd
		return True

	def set_cond(self, cond):
		self.cond = cond
		return True

	def set(self, cmd, cond="", bCond=False):
		self.cmd = cmd
		self.cond = cond
		self.bCond = bCond
		return True

	def copy(self):
		result = pQue(self.cmd, self.cond, self.bCond)
		result._items = self._items.copy()
		result._head = self._head
		result.pc = self.pc
		result.skip = self.skip
		return result