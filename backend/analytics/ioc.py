import yaml
import ipaddress
import re
from typing import Dict, Any, List, Optional

class IOCMatcher:
    """
    A class to load and match Indicators of Compromise (IOCs) against log records.
    """
    def __init__(self, ioc_config: Dict[str, Any]):
        """
        Initializes the IOCMatcher with a configuration dictionary.

        Args:
            ioc_config (Dict[str, Any]): A dictionary containing IOCs. Expected keys:
                                         'cidrs', 'asn', 'regex' (with 'uri' and 'ua' subkeys),
                                         'country', 'ua', 'uri'.
        """
        self.cidrs = [ipaddress.ip_network(cidr) for cidr in ioc_config.get('cidrs', [])]
        self.asns = set(ioc_config.get('asn', [])) # TODO: Implement ASN lookup (requires external data)
        self.countries = set(ioc_config.get('country', []))
        self.exact_ua = set(ioc_config.get('ua', []))
        self.exact_uri = set(ioc_config.get('uri', []))

        # Compile regexes for performance
        self.regex_ua = [re.compile(p, re.IGNORECASE) for p in ioc_config.get('regex', {}).get('ua', [])]
        self.regex_uri = [re.compile(p, re.IGNORECASE) for p in ioc_config.get('regex', {}).get('uri', [])]

    def _match_ip_cidr(self, ip_str: Optional[str]) -> Optional[str]:
        """Checks if an IP address matches any of the configured CIDR ranges."""
        if not ip_str:
            return None
        try:
            addr = ipaddress.ip_address(ip_str)
            for net in self.cidrs:
                if addr in net:
                    return f"CIDR:{net}"
            return None
        except ValueError:
            # Invalid IP string, ignore
            return None

    def _match_country(self, country_code: Optional[str]) -> Optional[str]:
        """Checks if a country code is in the IOC list."""
        if not country_code:
            return None
        return f"Country:{country_code}" if country_code in self.countries else None

    def _match_ua_exact(self, user_agent: Optional[str]) -> Optional[str]:
        """Checks for an exact match on the User-Agent string."""
        if not user_agent:
            return None
        return f"UA_Exact:{user_agent}" if user_agent in self.exact_ua else None

    def _match_uri_exact(self, uri: Optional[str]) -> Optional[str]:
        """Checks for an exact match on the URI string."""
        if not uri:
            return None
        return f"URI_Exact:{uri}" if uri in self.exact_uri else None

    def _match_ua_regex(self, user_agent: Optional[str]) -> Optional[str]:
        """Checks if a User-Agent matches any of the configured regexes."""
        if not user_agent:
            return None
        for pattern in self.regex_ua:
            if pattern.search(user_agent):
                return f"UA_Regex:{pattern.pattern}"
        return None

    def _match_uri_regex(self, uri: Optional[str]) -> Optional[str]:
        """Checks if a URI matches any of the configured regexes."""
        if not uri:
            return None
        for pattern in self.regex_uri:
            if pattern.search(uri):
                return f"URI_Regex:{pattern.pattern}"
        return None

    def match(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Matches a log record against all loaded IOCs.

        Args:
            record (Dict[str, Any]): A log record dictionary. Expected keys:
                                     'client_ip', 'country', 'user_agent', 'uri'.

        Returns:
            Dict[str, Any]: A dictionary with 'matched' (bool) and 'rules' (List[str])
                            indicating which IOCs were matched.
        """
        matched_rules = []

        # IP CIDR matching
        ip_match = self._match_ip_cidr(record.get('client_ip'))
        if ip_match:
            matched_rules.append(ip_match)

        # Country matching
        country_match = self._match_country(record.get('country'))
        if country_match:
            matched_rules.append(country_match)

        # User-Agent matching
        ua_exact_match = self._match_ua_exact(record.get('user_agent'))
        if ua_exact_match:
            matched_rules.append(ua_exact_match)
        ua_regex_match = self._match_ua_regex(record.get('user_agent'))
        if ua_regex_match:
            matched_rules.append(ua_regex_match)

        # URI matching
        uri_exact_match = self._match_uri_exact(record.get('uri'))
        if uri_exact_match:
            matched_rules.append(uri_exact_match)
        uri_regex_match = self._match_uri_regex(record.get('uri'))
        if uri_regex_match:
            matched_rules.append(uri_regex_match)

        # TODO: Implement ASN matching if ASN data is available.
        # asn_match = self._match_asn(record.get('asn'))
        # if asn_match:
        #     matched_rules.append(asn_match)

        return {"matched": bool(matched_rules), "rules": matched_rules}

def load_ioc(path: str = "config/ioc.yml") -> IOCMatcher:
    """
    Loads IOC configuration from a YAML file and returns an IOCMatcher instance.

    Args:
        path (str): The file path to the IOC YAML configuration.

    Returns:
        IOCMatcher: An instance of IOCMatcher initialized with the loaded configuration.

    Raises:
        FileNotFoundError: If the specified YAML file does not exist.
        yaml.YAMLError: If there is an error parsing the YAML file.
    """
    try:
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        return IOCMatcher(config)
    except FileNotFoundError:
        print(f"Error: IOC configuration file not found at {path}")
        raise
    except yaml.YAMLError as e:
        print(f"Error parsing IOC YAML file {path}: {e}")
        raise

# Example Usage:
if __name__ == '__main__':
    # Create a dummy ioc.yml for testing
    dummy_ioc_content = """
cidrs:
  - '192.168.1.0/24'
  - '10.0.0.1/32'
country:
  - 'KP'
  - 'RU'
ua:
  - 'BadBot'
uri:
  - '/admin.php'
regex:
  ua:
    - '(?i)sqlmap'
  uri:
    - '(?i)union select'
    """
    with open('config/ioc.yml', 'w') as f:
        f.write(dummy_ioc_content)

    try:
        matcher = load_ioc(path='config/ioc.yml')

        # Test records
        record1 = {'client_ip': '192.168.1.10', 'country': 'US', 'user_agent': 'Mozilla', 'uri': '/index.html'}
        record2 = {'client_ip': '10.0.0.1', 'country': 'KP', 'user_agent': 'BadBot', 'uri': '/admin.php'}
        record3 = {'client_ip': '203.0.113.5', 'country': 'RU', 'user_agent': 'sqlmap/1.0', 'uri': '/search?q=union+select+1'}
        record4 = {'client_ip': '172.16.0.1', 'country': 'JP', 'user_agent': 'GoodBot', 'uri': '/api/v1'}

        print(f"Matching record1: {matcher.match(record1)}")
        print(f"Matching record2: {matcher.match(record2)}")
        print(f"Matching record3: {matcher.match(record3)}")
        print(f"Matching record4: {matcher.match(record4)}")

    except Exception as e:
        print(f"An error occurred during example usage: {e}")

    # Clean up dummy file
    os.remove('config/ioc.yml')