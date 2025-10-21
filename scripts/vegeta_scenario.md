# Vegeta Load Testing Scenario

This document provides a basic scenario for using `vegeta` to generate test traffic against an endpoint protected by WAF.

## 1. Install Vegeta

Follow the installation instructions from the official repository:
[https://github.com/tsenart/vegeta](https://github.com/tsenart/vegeta)

## 2. Define Targets

Create a file named `targets.txt`. Each line represents a request target.

**Example `targets.txt`:**

```
# Benign Traffic
GET https://<your-api-gateway-endpoint>/items/1
GET https://<your-api-gateway-endpoint>/items/2
GET https://<your-api-gateway-endpoint>/items/3

# Suspicious Traffic
GET https://<your-api-gateway-endpoint>/api/users?id=1'
GET https://<your-api-gateway-endpoint>/api/users?id=' OR 1=1
GET https://<your-api-gateway-endpoint>/../../etc/passwd
```

## 3. Run Attack

Use the `vegeta attack` command.

```bash
# Attack with 10 requests per second for 30 seconds
vegeta attack -targets=targets.txt -rate=10/s -duration=30s | vegeta report

# To simulate a sudden burst (e.g., 500 requests)
vegeta attack -targets=targets.txt -rate=0 -duration=1s -max-workers=100 | vegeta report
```

## 4. Observe

While the attack is running, you should be able to:
1.  See the traffic in the WAF logs.
2.  Trigger the anomaly detection Lambda (if the timing aligns).
3.  Receive an SNS notification about the suspicious traffic patterns.
