import yaml
import ipaddress
import re

# TODO:
# - Add support for loading IOCs from S3 for dynamic updates.
# - Implement ASN lookup (requires a GeoIP database like MaxMind).

class IOCMatcher:
    """
    A class to load and match Indicators of Compromise (IOCs).
    """
    def __init__(self, ioc_config: dict):
        self.cidrs = [ipaddress.ip_network(cidr) for cidr in ioc_config.get('cidrs', [])]
        self.asns = set(ioc_config.get('asn', []))
        self.countries = set(ioc_config.get('country', []))
        self.exact_ua = set(ioc_config.get('ua', []))
        self.exact_uri = set(ioc_config.get('uri', []))
        
        # Compile regexes for performance
        self.regex_ua = [re.compile(p) for p in ioc_config.get('regex', {}).get('ua', [])]
        self.regex_uri = [re.compile(p) for p in ioc_config.get('regex', {}).get('uri', [])]

    def match_ip(self, ip_str: str) -> bool:
        """Checks if an IP address matches any of the configured CIDR ranges."""
        if not ip_str: return False
        try:
            addr = ipaddress.ip_address(ip_str)
            return any(addr in net for net in self.cidrs)
        except ValueError:
            return False # Invalid IP string

    def match_country(self, country_code: str) -> bool:
        """Checks if a country code is in the IOC list."""
        return country_code in self.countries

    def match_ua_exact(self, user_agent: str) -> bool:
        """Checks for an exact match on the User-Agent string."""
        return user_agent in self.exact_ua

    def match_uri_exact(self, uri: str) -> bool:
        """Checks for an exact match on the URI string."""
        return uri in self.exact_uri

    def match_ua(self, user_agent: str) -> bool:
        """Checks if a User-Agent matches any of the configured regexes."""
        if not user_agent: return False
        return any(p.search(user_agent) for p in self.regex_ua)

    def match_uri(self, uri: str) -> bool:
        """Checks if a URI matches any of the configured regexes."""
        if not uri: return False
        return any(p.search(uri) for p in self.regex_uri)

    def find_matches(self, feature_vector: dict) -> list:
        """
        Checks a feature vector (a row from Athena results) against all IOCs.
        Returns a list of matches found.
        """
        # TODO: Implement the logic to iterate through a feature vector
        # and return a list of dicts describing any matches.
        matches = []
        # Example:
        # if self.match_ip(feature_vector.get('ip')):
        #     matches.append({'type': 'cidr', 'value': feature_vector.get('ip')})
        return matches

def load_from_file(filepath: str) -> IOCMatcher:
    """Loads IOC configuration from a YAML file."""
    with open(filepath, 'r') as f:
        config = yaml.safe_load(f)
    return IOCMatcher(config)
