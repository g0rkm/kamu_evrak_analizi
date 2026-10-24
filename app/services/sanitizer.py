import re
import html

class Sanitizer:
    DANGEROUS_PATTERNS = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'<iframe[^>]*>', re.IGNORECASE),
        re.compile(r'<object[^>]*>', re.IGNORECASE),
        re.compile(r'<embed[^>]*>', re.IGNORECASE),
    ]
    
    SQL_PATTERNS = [
        re.compile(r"('\s*(OR|AND)\s+\d+\s*=\s*\d+)", re.IGNORECASE),
        re.compile(r"(UNION\s+SELECT)", re.IGNORECASE),
        re.compile(r"(DROP\s+TABLE)", re.IGNORECASE),
        re.compile(r"(INSERT\s+INTO)", re.IGNORECASE),
        re.compile(r"(DELETE\s+FROM)", re.IGNORECASE),
    ]
    
    @staticmethod
    def sanitize_html(text: str) -> str:
        if not text:
            return text
        return html.escape(text)
    
    @classmethod
    def check_xss(cls, text: str) -> dict:
        if not text:
            return {"safe": True, "threats": []}
        threats = []
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(text):
                threats.append(f"XSS pattern detected: {pattern.pattern[:50]}")
        return {"safe": len(threats) == 0, "threats": threats}
    
    @classmethod
    def check_sql_injection(cls, text: str) -> dict:
        if not text:
            return {"safe": True, "threats": []}
        threats = []
        for pattern in cls.SQL_PATTERNS:
            if pattern.search(text):
                threats.append(f"SQL injection pattern: {pattern.pattern[:50]}")
        return {"safe": len(threats) == 0, "threats": threats}
    
    @classmethod
    def sanitize_input(cls, text: str) -> dict:
        if not text:
            return {"original": text, "sanitized": text, "safe": True, "threats": []}
        xss = cls.check_xss(text)
        sql = cls.check_sql_injection(text)
        all_threats = xss["threats"] + sql["threats"]
        sanitized = cls.sanitize_html(text)
        return {
            "original_length": len(text),
            "sanitized": sanitized,
            "safe": len(all_threats) == 0,
            "threats": all_threats
        }
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        if not filename:
            return "unnamed"
        safe = re.sub(r'[^\w\s\-.]', '', filename)
        safe = safe.strip('. ')
        return safe[:255] if safe else "unnamed"
