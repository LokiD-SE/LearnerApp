"""Data for the WSTG and ASVS lesson (owasp-wstg-and-asvs) - shared by its tests, not an exercise.

- ``WSTG_V42_CHECKLIST``: the testing checklist table of the OWASP Web Security Testing Guide v4.2, copied
  unchanged from ``checklist/Testing_Checklist.md`` at tag ``v4.2`` of github.com/OWASP/wstg (CC BY-SA 4.0).
  Note what it really contains: category rows in bold, some category ids that differ from their tests'
  prefix (``WSTG-BUSLOGIC`` heads ``WSTG-BUSL-..`` tests, ``WSTG-CLIENT`` heads ``WSTG-CLNT-..``).
- ``ASVS_500_SAMPLE``: 23 requirements of the OWASP ASVS 5.0.0 (release tag ``v5.0.0_release``, file
  ``OWASP_Application_Security_Verification_Standard_5.0.0_en.csv``, CC BY-SA 4.0) as dicts with the CSV's
  column names: ``req_id``, ``chapter_name``, ``section_name``, ``L`` (the level, as text) and ``req_description``.
- ``FLAW_MAP``: for each flaw of the practice portal (support/sandpay_vuln.py), the WSTG v4.2 test ids that
  test it and the ASVS 5.0.0 requirements it breaks. This mapping is this lesson's judgement, not OWASP's;
  an empty WSTG list means v4.2 has no test for it (the development version of the WSTG adds some).
"""

WSTG_V42_CHECKLIST = """\
| Test ID           | Test Name                                                                  | Status | Notes |
|-------------------|----------------------------------------------------------------------------|--------|-------|
| **WSTG-INFO**     | **Information Gathering**                                                  |        |       |
| WSTG-INFO-01      | Conduct Search Engine Discovery and Reconnaissance for Information Leakage |        |       |
| WSTG-INFO-02      | Fingerprint Web Server                                                     |        |       |
| WSTG-INFO-03      | Review Webserver Metafiles for Information Leakage                         |        |       |
| WSTG-INFO-04      | Enumerate Applications on Webserver                                        |        |       |
| WSTG-INFO-05      | Review Webpage Content for Information Leakage                             |        |       |
| WSTG-INFO-06      | Identify Application Entry Points                                          |        |       |
| WSTG-INFO-07      | Map Execution Paths Through Application                                    |        |       |
| WSTG-INFO-08      | Fingerprint Web Application Framework                                      |        |       |
| WSTG-INFO-09      | Fingerprint Web Application                                                |        |       |
| WSTG-INFO-10      | Map Application Architecture                                               |        |       |
| **WSTG-CONF**     | **Configuration and Deploy Management Testing**                            |        |       |
| WSTG-CONF-01      | Test Network Infrastructure Configuration                                  |        |       |
| WSTG-CONF-02      | Test Application Platform Configuration                                    |        |       |
| WSTG-CONF-03      | Test File Extensions Handling for Sensitive Information                    |        |       |
| WSTG-CONF-04      | Review Old Backup and Unreferenced Files for Sensitive Information         |        |       |
| WSTG-CONF-05      | Enumerate Infrastructure and Application Admin Interfaces                  |        |       |
| WSTG-CONF-06      | Test HTTP Methods                                                          |        |       |
| WSTG-CONF-07      | Test HTTP Strict Transport Security                                        |        |       |
| WSTG-CONF-08      | Test RIA Cross Domain Policy                                               |        |       |
| WSTG-CONF-09      | Test File Permission                                                       |        |       |
| WSTG-CONF-10      | Test for Subdomain Takeover                                                |        |       |
| WSTG-CONF-11      | Test Cloud Storage                                                         |        |       |
| **WSTG-IDNT**     | **Identity Management Testing**                                            |        |       |
| WSTG-IDNT-01      | Test Role Definitions                                                      |        |       |
| WSTG-IDNT-02      | Test User Registration Process                                             |        |       |
| WSTG-IDNT-03      | Test Account Provisioning Process                                          |        |       |
| WSTG-IDNT-04      | Testing for Account Enumeration and Guessable User Account                 |        |       |
| WSTG-IDNT-05      | Testing for Weak or Unenforced Username Policy                             |        |       |
| **WSTG-ATHN**     | **Authentication Testing**                                                 |        |       |
| WSTG-ATHN-01      | Testing for Credentials Transported over an Encrypted Channel              |        |       |
| WSTG-ATHN-02      | Testing for Default Credentials                                            |        |       |
| WSTG-ATHN-03      | Testing for Weak Lock Out Mechanism                                        |        |       |
| WSTG-ATHN-04      | Testing for Bypassing Authentication Schema                                |        |       |
| WSTG-ATHN-05      | Testing for Vulnerable Remember Password                                   |        |       |
| WSTG-ATHN-06      | Testing for Browser Cache Weakness                                         |        |       |
| WSTG-ATHN-07      | Testing for Weak Password Policy                                           |        |       |
| WSTG-ATHN-08      | Testing for Weak Security Question Answer                                  |        |       |
| WSTG-ATHN-09      | Testing for Weak Password Change or Reset Functionalities                  |        |       |
| WSTG-ATHN-10      | Testing for Weaker Authentication in Alternative Channel                   |        |       |
| **WSTG-ATHZ**     | **Authorization Testing**                                                  |        |       |
| WSTG-ATHZ-01      | Testing Directory Traversal File Include                                   |        |       |
| WSTG-ATHZ-02      | Testing for Bypassing Authorization Schema                                 |        |       |
| WSTG-ATHZ-03      | Testing for Privilege Escalation                                           |        |       |
| WSTG-ATHZ-04      | Testing for Insecure Direct Object References                              |        |       |
| **WSTG-SESS**     | **Session Management Testing**                                             |        |       |
| WSTG-SESS-01      | Testing for Session Management Schema                                      |        |       |
| WSTG-SESS-02      | Testing for Cookies Attributes                                             |        |       |
| WSTG-SESS-03      | Testing for Session Fixation                                               |        |       |
| WSTG-SESS-04      | Testing for Exposed Session Variables                                      |        |       |
| WSTG-SESS-05      | Testing for Cross Site Request Forgery                                     |        |       |
| WSTG-SESS-06      | Testing for Logout Functionality                                           |        |       |
| WSTG-SESS-07      | Testing Session Timeout                                                    |        |       |
| WSTG-SESS-08      | Testing for Session Puzzling                                               |        |       |
| WSTG-SESS-09      | Testing for Session Hijacking                                              |        |       |
| **WSTG-INPV**     | **Input Validation Testing**                                               |        |       |
| WSTG-INPV-01      | Testing for Reflected Cross Site Scripting                                 |        |       |
| WSTG-INPV-02      | Testing for Stored Cross Site Scripting                                    |        |       |
| WSTG-INPV-03      | Testing for HTTP Verb Tampering                                            |        |       |
| WSTG-INPV-04      | Testing for HTTP Parameter pollution                                       |        |       |
| WSTG-INPV-05      | Testing for SQL Injection                                                  |        |       |
| WSTG-INPV-06      | Testing for LDAP Injection                                                 |        |       |
| WSTG-INPV-07      | Testing for XML Injection                                                  |        |       |
| WSTG-INPV-08      | Testing for SSI Injection                                                  |        |       |
| WSTG-INPV-09      | Testing for XPath Injection                                                |        |       |
| WSTG-INPV-10      | Testing for IMAP SMTP Injection                                            |        |       |
| WSTG-INPV-11      | Testing for Code Injection                                                 |        |       |
| WSTG-INPV-12      | Testing for Command Injection                                              |        |       |
| WSTG-INPV-13      | Testing for Format String Injection                                        |        |       |
| WSTG-INPV-14      | Testing for Incubated Vulnerabilities                                      |        |       |
| WSTG-INPV-15      | Testing for HTTP Splitting Smuggling                                       |        |       |
| WSTG-INPV-16      | Testing for HTTP Incoming Requests                                         |        |       |
| WSTG-INPV-17      | Testing for Host Header Injection                                          |        |       |
| WSTG-INPV-18      | Testing for Server-side Template Injection                                 |        |       |
| WSTG-INPV-19      | Testing for Server-Side Request Forgery                                    |        |       |
| **WSTG-ERRH**     | **Error Handling**                                                         |        |       |
| WSTG-ERRH-01      | Testing for Improper Error Handling                                        |        |       |
| WSTG-ERRH-02      | Testing for Stack Traces                                                   |        |       |
| **WSTG-CRYP**     | **Cryptography**                                                           |        |       |
| WSTG-CRYP-01      | Testing for Weak Transport Layer Security                                  |        |       |
| WSTG-CRYP-02      | Testing for Padding Oracle                                                 |        |       |
| WSTG-CRYP-03      | Testing for Sensitive Information Sent Via Unencrypted Channels            |        |       |
| WSTG-CRYP-04      | Testing for Weak Encryption                                                |        |       |
| **WSTG-BUSLOGIC** | **Business Logic Testing**                                                 |        |       |
| WSTG-BUSL-01      | Test Business Logic Data Validation                                        |        |       |
| WSTG-BUSL-02      | Test Ability to Forge Requests                                             |        |       |
| WSTG-BUSL-03      | Test Integrity Checks                                                      |        |       |
| WSTG-BUSL-04      | Test for Process Timing                                                    |        |       |
| WSTG-BUSL-05      | Test Number of Times a Function Can be Used Limits                         |        |       |
| WSTG-BUSL-06      | Testing for the Circumvention of Work Flows                                |        |       |
| WSTG-BUSL-07      | Test Defenses Against Application Misuse                                   |        |       |
| WSTG-BUSL-08      | Test Upload of Unexpected File Types                                       |        |       |
| WSTG-BUSL-09      | Test Upload of Malicious Files                                             |        |       |
| **WSTG-CLIENT**   | **Client-side Testing**                                                    |        |       |
| WSTG-CLNT-01      | Testing for DOM based Cross Site Scripting                                 |        |       |
| WSTG-CLNT-02      | Testing for JavaScript Execution                                           |        |       |
| WSTG-CLNT-03      | Testing for HTML Injection                                                 |        |       |
| WSTG-CLNT-04      | Testing for Client-side URL Redirect                                       |        |       |
| WSTG-CLNT-05      | Testing for CSS Injection                                                  |        |       |
| WSTG-CLNT-06      | Testing for Client-side Resource Manipulation                              |        |       |
| WSTG-CLNT-07      | Test Cross Origin Resource Sharing                                         |        |       |
| WSTG-CLNT-08      | Testing for Cross Site Flashing                                            |        |       |
| WSTG-CLNT-09      | Testing for Clickjacking                                                   |        |       |
| WSTG-CLNT-10      | Testing WebSockets                                                         |        |       |
| WSTG-CLNT-11      | Test Web Messaging                                                         |        |       |
| WSTG-CLNT-12      | Test Browser Storage                                                       |        |       |
| WSTG-CLNT-13      | Testing for Cross Site Script Inclusion                                    |        |       |
| **WSTG-APIT**     | **API Testing**                                                            |        |       |
| WSTG-APIT-01      | Testing GraphQL                                                            |        |       |
"""

ASVS_500_SAMPLE = [
    {
        "req_id": 'V1.2.1',
        "chapter_name": 'Encoding and Sanitization',
        "section_name": 'Injection Prevention',
        "L": "1",
        "req_description": 'Verify that output encoding for an HTTP response, HTML document, or XML document is relevant for the context required, such as encoding the relevant characters for HTML elements, HTML attributes, HTML comments, CSS, or HTTP header fields, to avoid changing the message or document structure.',
    },
    {
        "req_id": 'V1.2.4',
        "chapter_name": 'Encoding and Sanitization',
        "section_name": 'Injection Prevention',
        "L": "1",
        "req_description": 'Verify that data selection or database queries (e.g., SQL, HQL, NoSQL, Cypher) use parameterized queries, ORMs, entity frameworks, or are otherwise protected from SQL Injection and other database injection attacks. This is also relevant when writing stored procedures.',
    },
    {
        "req_id": 'V1.3.6',
        "chapter_name": 'Encoding and Sanitization',
        "section_name": 'Sanitization',
        "L": "2",
        "req_description": 'Verify that the application protects against Server-side Request Forgery (SSRF) attacks, by validating untrusted data against an allowlist of protocols, domains, paths and ports and sanitizing potentially dangerous characters before using the data to call another service.',
    },
    {
        "req_id": 'V3.3.1',
        "chapter_name": 'Web Frontend Security',
        "section_name": 'Cookie Setup',
        "L": "1",
        "req_description": "Verify that cookies have the 'Secure' attribute set, and if the '\\__Host-' prefix is not used for the cookie name, the '__Secure-' prefix must be used for the cookie name.",
    },
    {
        "req_id": 'V3.3.2',
        "chapter_name": 'Web Frontend Security',
        "section_name": 'Cookie Setup',
        "L": "2",
        "req_description": "Verify that each cookie's 'SameSite' attribute value is set according to the purpose of the cookie, to limit exposure to user interface redress attacks and browser-based request forgery attacks, commonly known as cross-site request forgery (CSRF).",
    },
    {
        "req_id": 'V3.3.4',
        "chapter_name": 'Web Frontend Security',
        "section_name": 'Cookie Setup',
        "L": "2",
        "req_description": "Verify that if the value of a cookie is not meant to be accessible to client-side scripts (such as a session token), the cookie must have the 'HttpOnly' attribute set and the same value (e. g. session token) must only be transferred to the client via the 'Set-Cookie' header field.",
    },
    {
        "req_id": 'V3.4.1',
        "chapter_name": 'Web Frontend Security',
        "section_name": 'Browser Security Mechanism Headers',
        "L": "1",
        "req_description": 'Verify that a Strict-Transport-Security header field is included on all responses to enforce an HTTP Strict Transport Security (HSTS) policy. A maximum age of at least 1 year must be defined, and for L2 and up, the policy must apply to all subdomains as well.',
    },
    {
        "req_id": 'V3.4.3',
        "chapter_name": 'Web Frontend Security',
        "section_name": 'Browser Security Mechanism Headers',
        "L": "2",
        "req_description": "Verify that HTTP responses include a Content-Security-Policy response header field which defines directives to ensure the browser only loads and executes trusted content or resources, in order to limit execution of malicious JavaScript. As a minimum, a global policy must be used which includes the directives object-src 'none' and base-uri 'none' and defines either an allowlist or uses nonces or hashes. For an L3 application, a per-response policy with nonces or hashes must be defined.",
    },
    {
        "req_id": 'V3.4.4',
        "chapter_name": 'Web Frontend Security',
        "section_name": 'Browser Security Mechanism Headers',
        "L": "2",
        "req_description": "Verify that all HTTP responses contain an 'X-Content-Type-Options: nosniff' header field. This instructs browsers not to use content sniffing and MIME type guessing for the given response, and to require the response's Content-Type header field value to match the destination resource. For example, the response to a request for a style is only accepted if the response's Content-Type is 'text/css'. This also enables the use of the Cross-Origin Read Blocking (CORB) functionality by the browser.",
    },
    {
        "req_id": 'V3.5.1',
        "chapter_name": 'Web Frontend Security',
        "section_name": 'Browser Origin Separation',
        "L": "1",
        "req_description": 'Verify that, if the application does not rely on the CORS preflight mechanism to prevent disallowed cross-origin requests to use sensitive functionality, these requests are validated to ensure they originate from the application itself. This may be done by using and validating anti-forgery tokens or requiring extra HTTP header fields that are not CORS-safelisted request-header fields. This is to defend against browser-based request forgery attacks, commonly known as cross-site request forgery (CSRF).',
    },
    {
        "req_id": 'V3.7.2',
        "chapter_name": 'Web Frontend Security',
        "section_name": 'Other Browser Security Considerations',
        "L": "2",
        "req_description": 'Verify that the application will only automatically redirect the user to a different hostname or domain (which is not controlled by the application) where the destination appears on an allowlist.',
    },
    {
        "req_id": 'V5.3.2',
        "chapter_name": 'File Handling',
        "section_name": 'File Storage',
        "L": "1",
        "req_description": 'Verify that when the application creates file paths for file operations, instead of user-submitted filenames, it uses internally generated or trusted data, or if user-submitted filenames or file metadata must be used, strict validation and sanitization must be applied. This is to protect against path traversal, local or remote file inclusion (LFI, RFI), and server-side request forgery (SSRF) attacks.',
    },
    {
        "req_id": 'V6.3.1',
        "chapter_name": 'Authentication',
        "section_name": 'General Authentication Security',
        "L": "1",
        "req_description": "Verify that controls to prevent attacks such as credential stuffing and password brute force are implemented according to the application's security documentation.",
    },
    {
        "req_id": 'V8.2.2',
        "chapter_name": 'Authorization',
        "section_name": 'General Authorization Design',
        "L": "1",
        "req_description": 'Verify that the application ensures that data-specific access is restricted to consumers with explicit permissions to specific data items to mitigate insecure direct object reference (IDOR) and broken object level authorization (BOLA).',
    },
    {
        "req_id": 'V8.2.3',
        "chapter_name": 'Authorization',
        "section_name": 'General Authorization Design',
        "L": "2",
        "req_description": 'Verify that the application ensures that field-level access is restricted to consumers with explicit permissions to specific fields to mitigate broken object property level authorization (BOPLA).',
    },
    {
        "req_id": 'V9.1.1',
        "chapter_name": 'Self-contained Tokens',
        "section_name": 'Token source and integrity',
        "L": "1",
        "req_description": "Verify that self-contained tokens are validated using their digital signature or MAC to protect against tampering before accepting the token's contents.",
    },
    {
        "req_id": 'V9.1.2',
        "chapter_name": 'Self-contained Tokens',
        "section_name": 'Token source and integrity',
        "L": "1",
        "req_description": "Verify that only algorithms on an allowlist can be used to create and verify self-contained tokens, for a given context. The allowlist must include the permitted algorithms, ideally only either symmetric or asymmetric algorithms, and must not include the 'None' algorithm. If both symmetric and asymmetric must be supported, additional controls will be needed to prevent key confusion.",
    },
    {
        "req_id": 'V11.4.2',
        "chapter_name": 'Cryptography',
        "section_name": 'Hashing and Hash-based Functions',
        "L": "2",
        "req_description": 'Verify that passwords are stored using an approved, computationally intensive, key derivation function (also known as a "password hashing function"), with parameter settings configured based on current guidance. The settings should balance security and performance to make brute-force attacks sufficiently challenging for the required level of security.',
    },
    {
        "req_id": 'V13.4.6',
        "chapter_name": 'Configuration',
        "section_name": 'Unintended Information Leakage',
        "L": "3",
        "req_description": 'Verify that the application does not expose detailed version information of backend components.',
    },
    {
        "req_id": 'V15.3.1',
        "chapter_name": 'Secure Coding and Architecture',
        "section_name": 'Defensive Coding',
        "L": "1",
        "req_description": 'Verify that the application only returns the required subset of fields from a data object. For example, it should not return an entire data object, as some individual fields should not be accessible to users.',
    },
    {
        "req_id": 'V15.3.3',
        "chapter_name": 'Secure Coding and Architecture',
        "section_name": 'Defensive Coding',
        "L": "2",
        "req_description": 'Verify that the application has countermeasures to protect against mass assignment attacks by limiting allowed fields per controller and action, e.g., it is not possible to insert or update a field value when it was not intended to be part of that action.',
    },
    {
        "req_id": 'V16.2.5',
        "chapter_name": 'Security Logging and Error Handling',
        "section_name": 'General Logging',
        "L": "2",
        "req_description": "Verify that when logging sensitive data, the application enforces logging based on the data's protection level. For example, it may not be allowed to log certain data, such as credentials or payment details. Other data, such as session tokens, may only be logged by being hashed or masked, either in full or partially.",
    },
    {
        "req_id": 'V16.5.1',
        "chapter_name": 'Security Logging and Error Handling',
        "section_name": 'Error Handling',
        "L": "2",
        "req_description": 'Verify that a generic message is returned to the consumer when an unexpected or security-sensitive error occurs, ensuring no exposure of sensitive internal system data such as stack traces, queries, secret keys, and tokens.',
    },
]

FLAW_MAP = {
    "idor": {"wstg": ["WSTG-ATHZ-04"], "asvs": ["V8.2.2"]},
    "mass-assignment": {"wstg": ["WSTG-ATHZ-03"], "asvs": ["V15.3.3", "V8.2.3"]},
    "sqli": {"wstg": ["WSTG-INPV-05"], "asvs": ["V1.2.4"]},
    "xss-reflected": {"wstg": ["WSTG-INPV-01"], "asvs": ["V1.2.1"]},
    "xss-stored": {"wstg": ["WSTG-INPV-02"], "asvs": ["V1.2.1"]},
    "path-traversal": {"wstg": ["WSTG-ATHZ-01"], "asvs": ["V5.3.2"]},
    "open-redirect": {"wstg": ["WSTG-CLNT-04"], "asvs": ["V3.7.2"]},
    "ssrf": {"wstg": ["WSTG-INPV-19"], "asvs": ["V1.3.6"]},
    "csrf": {"wstg": ["WSTG-SESS-05"], "asvs": ["V3.5.1", "V3.3.2"]},
    "weak-session": {"wstg": ["WSTG-SESS-02"], "asvs": ["V3.3.1", "V3.3.4"]},
    "no-rate-limit": {"wstg": ["WSTG-ATHN-03"], "asvs": ["V6.3.1"]},
    "jwt-none": {"wstg": [], "asvs": ["V9.1.1", "V9.1.2"]},
    "weak-hash": {"wstg": ["WSTG-CRYP-04"], "asvs": ["V11.4.2"]},
    "verbose-errors": {"wstg": ["WSTG-ERRH-01"], "asvs": ["V16.5.1"]},
    "missing-headers": {"wstg": ["WSTG-INFO-02"], "asvs": ["V3.4.3", "V3.4.4", "V13.4.6"]},
    "data-exposure": {"wstg": [], "asvs": ["V15.3.1"]},
    "secret-logging": {"wstg": [], "asvs": ["V16.2.5"]},
}
