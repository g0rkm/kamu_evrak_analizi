import re
import collections

class TextAnalyzer:
    @staticmethod
    def analyze(text: str) -> dict:
        if not text or not text.strip():
            return {
                'char_count': 0,
                'word_count': 0,
                'sentence_count': 0,
                'paragraph_count': 0,
                'avg_word_length': 0,
                'unique_words': 0,
                'top_words': [],
                'readability_score': 0
            }
        
        words = re.findall(r'\b\w+\b', text.lower())
        sentences = re.split(r'[.!?]+', text)
        sentences = [s for s in sentences if s.strip()]
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        
        word_freq = collections.Counter(words)
        stop_words = {
            've', 'bir', 'bu', 'da', 'de', 'ile', 'icin', 'olan', 'gibi', 'ise', 
            'ne', 'var', 'mi', 'ben', 'sen', 'o', 'biz', 'siz', 'onlar', 'ama', 
            'fakat', 'veya', 'ya', 'hem', 'ki', 'cok', 'daha', 'en', 'her', 'tum', 
            'bazi', 'su', 'olarak', 'icinde', 'uzerinde', 'kadar', 'sonra', 'once', 
            'eger', 'ancak', 'hala', 'artik'
        }
        
        meaningful = {w: c for w, c in word_freq.items() if w not in stop_words and len(w) > 2}
        top = sorted(meaningful.items(), key=lambda x: x[1], reverse=True)[:10]
        
        avg_wl = sum(len(w) for w in words) / len(words) if words else 0
        avg_sl = len(words) / len(sentences) if sentences else 0
        readability = max(0, min(100, 100 - (avg_sl * 2 + avg_wl * 5)))
        
        return {
            'char_count': len(text),
            'word_count': len(words),
            'sentence_count': len(sentences),
            'paragraph_count': len(paragraphs),
            'avg_word_length': round(avg_wl, 1),
            'avg_sentence_length': round(avg_sl, 1),
            'unique_words': len(set(words)),
            'vocabulary_richness': round(len(set(words)) / len(words), 3) if words else 0,
            'top_words': [{'word': w, 'count': c} for w, c in top],
            'readability_score': round(readability, 1)
        }
