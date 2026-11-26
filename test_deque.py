import unittest

from deque import Deque, Queue, Stack, pQue


class DequeTests(unittest.TestCase):
	def test_both_ends_and_peeking(self):
		queue = Deque([2, 3])
		queue.push_front(1)
		queue.push(4)
		self.assertEqual(list(queue), [1, 2, 3, 4])
		self.assertEqual((queue.peek(), queue.peek_back()), (1, 4))
		self.assertEqual((queue.pop(), queue.pop_back()), (1, 4))
		self.assertEqual((queue.size(), len(queue), queue.is_empty()), (2, 2, False))
		self.assertEqual((queue.pop(), queue.pop()), (2, 3))
		self.assertTrue(queue.is_empty())
		with self.assertRaises(IndexError):
			queue.pop()
		with self.assertRaises(IndexError):
			queue.peek_back()

	def test_bulk_operations_and_copies(self):
		queue = Deque([1, 2])
		source = Deque([3, 4])
		queue.push_queue(source)
		self.assertEqual(queue.to_array(), [1, 2, 3, 4])
		self.assertTrue(source.is_empty())
		queue.push_front_queue(Deque([5, 6]))
		self.assertEqual(queue.to_array(), [6, 5, 1, 2, 3, 4])
		self.assertIs(queue.peek_queue(), queue)
		self.assertEqual(queue.copy().to_array(), queue.to_array())
		self.assertEqual(queue.copy_reverse().to_array(), [4, 3, 2, 1, 5, 6])
		self.assertEqual(queue.pop_back_queue().to_array(), [4, 3, 2, 1, 5, 6])
		self.assertTrue(queue.is_empty())
		queue.push_queue(Deque([7, 8]))
		self.assertEqual(queue.pop_queue().to_array(), [7, 8])
		self.assertTrue(queue.is_empty())
		with self.assertRaises(ValueError):
			queue.push_queue(queue)

	def test_fifo_and_lifo_interfaces(self):
		for cls, expected in ((Queue, [1, 2, 3]), (Stack, [3, 2, 1])):
			self.assertIn(Deque, cls.__bases__)
			queue = cls()
			self.assertIsInstance(queue, Deque)
			for value in (1, 2, 3):
				queue.push(value)
			self.assertEqual(queue.peek(), expected[0])
			self.assertEqual([queue.pop(), queue.pop(), queue.pop()], expected)
			self.assertTrue(queue.is_empty())
			for name in ("push_front", "pop_back", "peek_back", "push_queue", "pop_queue", "to_array"):
				self.assertFalse(hasattr(queue, name))

	def test_program_queue_execution_and_metadata(self):
		queue = pQue("while", "$count < 2", True)
		self.assertIsInstance(queue, Deque)
		self.assertEqual((queue.cmd, queue.cond, queue.bCond, queue.skip), ("while", "$count < 2", True, False))
		self.assertTrue(queue.is_parked())
		self.assertEqual(queue.pc_index(), 0)
		queue.push("first")
		queue.push("second")
		with self.assertRaises(IndexError):
			queue.pc_item()
		self.assertTrue(queue.release())
		self.assertTrue(queue.is_start())
		self.assertEqual(queue.pc_item(), "first")
		self.assertEqual(queue.pc_item(), "second")
		self.assertTrue(queue.is_done())
		self.assertEqual(queue.to_array(), ["first", "second"])
		with self.assertRaises(IndexError):
			queue.pc_item()
		queue.restart()
		self.assertEqual(queue.pc_item(), "first")
		queue.skip = True
		queue.set("until", "$done", False)
		copy = queue.copy()
		self.assertEqual((copy.cmd, copy.cond, copy.bCond, copy.skip, copy.pc),
			("until", "$done", False, True, queue.pc))
		self.assertEqual(copy.pc_item(), "second")
		self.assertEqual(queue.pc_item(), "second")

	def test_program_counter_when_queue_changes(self):
		queue = pQue()
		self.assertTrue(queue.is_parked())
		self.assertFalse(queue.is_done())
		queue.release()
		self.assertTrue(queue.is_start())
		self.assertTrue(queue.is_done())
		queue.push("one")
		self.assertFalse(queue.is_done())
		self.assertEqual(queue.pc_item(), "one")
		queue.push("two")
		self.assertEqual(queue.pc_item(), "two")
		queue.restart()
		self.assertEqual(queue.pop(), "one")
		self.assertTrue(queue.is_parked())
		self.assertTrue(queue.increment_pc())
		self.assertEqual(queue.pc_item(), "two")
		queue.set_done()
		self.assertFalse(queue.increment_pc())


if __name__ == "__main__":
	unittest.main()