import unittest
import yaml
from backend.analytics.ioc import IOCMatcher

class TestIOCMatcher(unittest.TestCase):

    def setUp(self):
        """Set up a dummy IOC configuration."""
        self.ioc_config_str = """
cidrs:
  - '192.168.1.0/24'
asn:
  - 'AS15169'
regex:
  uri:
    - '/etc/passwd'
    - '(?i)SELECT.*FROM'
  ua:
    - '(?i)sqlmap'
country:
  - 'KP'
ua:
  - 'BadBot'
uri:
  - '/bad-path'
        """
        self.ioc_config = yaml.safe_load(self.ioc_config_str)
        self.matcher = IOCMatcher(self.ioc_config)

    def test_cidr_match(self):
        """Test CIDR matching logic."""
        self.assertTrue(self.matcher.match_ip('192.168.1.100'))
        self.assertFalse(self.matcher.match_ip('10.0.0.1'))

    def test_regex_match(self):
        """Test regex matching on URI and User-Agent."""
        self.assertTrue(self.matcher.match_uri('/etc/passwd'))
        self.assertTrue(self.matcher.match_uri('/path?query=SELECT%20*%20FROM%20users'))
        self.assertTrue(self.matcher.match_ua('sqlmap/1.5'))
        self.assertFalse(self.matcher.match_uri('/good-path'))

    def test_exact_match(self):
        """Test exact string matching."""
        self.assertTrue(self.matcher.match_country('KP'))
        self.assertTrue(self.matcher.match_ua_exact('BadBot'))
        self.assertTrue(self.matcher.match_uri_exact('/bad-path'))
        self.assertFalse(self.matcher.match_country('US'))


if __name__ == '__main__':
    unittest.main()
