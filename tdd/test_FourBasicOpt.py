import unittest
from FourBasicOpt import FourBasicOpt

class TestFourBasicOpt(unittest.TestCase):
    def setUp(self):
        self.fourBasicOpt = FourBasicOpt()

    def test_add(self):
        self.assertEqual(self.fourBasicOpt.add(1, 2), 3)

    def test_sub(self):
        self.assertEqual(self.fourBasicOpt.sub(1, 2), -1)

    def test_mul(self):
        self.assertEqual(self.fourBasicOpt.mul(1, 2), 2)

    def test_div(self):
        self.assertEqual(self.fourBasicOpt.div(1, 2), 0.5)

if __name__ == '__main__':
    unittest.main()