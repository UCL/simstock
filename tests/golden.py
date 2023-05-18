import unittest 
from filecmp import cmp 

class GoldenTestCase(unittest.TestCase):

    def assertGolden(self, path_got, path_expect):
        flag = cmp(path_got, path_expect, shallow=True)
        msg = '\033[1m'+'\n\nFile %s does not match %s'%(path_got, path_expect)+'\033[0m'
        self.assertEqual(flag, True, msg=msg) 
        
