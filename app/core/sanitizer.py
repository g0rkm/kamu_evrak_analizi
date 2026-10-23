import re
import html

class InputSanitizer:
    HTML_TAG_RE = re.compile(r'<[^>]+>')
    SCRIPT_RE = re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL)
    EVENT_HANDLER_RE = re.compile(r'\bon\w+\s*=', re.IGNORECASE)

    @staticmethod
    def sanitize_string(value: str) -> str:
        if not isinstance(value, str):
            return value
        value = InputSanitizer.SCRIPT_RE.sub('', value)
        value = html.escape(value)
        return value.strip()

    @staticmethod
    def sanitize_html(value: str) -> str:
        if not isinstance(value, str):
            return value
        value = InputSanitizer.SCRIPT_RE.sub('', value)
        value = InputSanitizer.EVENT_HANDLER_RE.sub('', value)
        return value.strip()

    @staticmethod
    def strip_tags(value: str) -> str:
        if not isinstance(value, str):
            return value
        return InputSanitizer.HTML_TAG_RE.sub('', value).strip()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        if not filename:
            return ''
        name = re.sub(r'[^\w\s\-.]', '', filename)
        name = re.sub(r'\.{2,}', '.', name)
        return name.strip()

    @staticmethod
    def is_safe_path(path: str) -> bool:
        dangerous = ['..', '~', '\\\\', '//']
        return not any(d in path for d in dangerous)
