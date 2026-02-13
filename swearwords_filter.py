class SwearWordsFilter:
    """Filter to detect and block inappropriate language"""
    
    # List of inappropriate words (expandable)
    SWEARWORDS_LIST = [
        # Explicit profanity
        'fuck', 'fucking', 'fucked', 'fucker', 'fck', 'fuk',
        'shit', 'shitting', 'bullshit', 'shitty', 'sht',
        'bitch', 'bitches', 'bitching', 'btch',
        'asshole', 'arsehole', 'ass', 'arse',
        'damn', 'damned', 'dammit',
        'bastard', 'crap', 'piss', 'nigger', 'nigga',
        
        # Insults and derogatory terms
        'stupid', 'idiot', 'dumb', 'moron', 'fool',
        'loser', 'pathetic', 'worthless', 'useless',
        'ugly', 'fat', 'disgusting', 'retard', 'retarded',
        
        # Hate speech
        'hate', 'kill yourself', 'die', 'death', 'kys'
        
        # Singapore context
        'chao', 'knn', 'ccb', 'cb', 'lan jiao', 'nabei', 'chee bai', 'kanina'
    ]
    
    # Variations and leetspeak patterns
    CHAR_REPLACEMENTS = {
        '@': 'a', '4': 'a', '3': 'e', '1': 'i', '!': 'i',
        '0': 'o', '$': 's', '7': 't', '+': 't', '5': 's',
        '8': 'b', '9': 'g', '*': '', '#': '', '&': ''
    }
    
    def __init__(self):
        """Initialize the filter with lowercase word list"""
        self.swearwords = [word.lower() for word in self.SWEARWORDS_LIST]
    
    def _normalize_text(self, text):
        """Normalize text by replacing leetspeak and special characters"""
        normalized = text.lower()
        for char, replacement in self.CHAR_REPLACEMENTS.items():
            normalized = normalized.replace(char, replacement)
        # Remove common separators used to bypass filters
        for sep in ['-', '_', '.', '*']:
            normalized = normalized.replace(sep, '')
        return normalized
    
    def contains_swearwords(self, text):
        """Check if text contains profanity. Returns: (bool, list of matched words)"""
        if not text or not text.strip():
            return False, []
        
        # Normalize text
        normalized = self._normalize_text(text)
        
        # Check against all words
        matched_words = []
        for word in self.swearwords:
            if word in normalized:
                matched_words.append(word)
        
        return len(matched_words) > 0, matched_words
    
    def filter_message(self, text, replacement='*'):
        """Filter profanity from text by replacing with asterisks. Returns: filtered text"""
        if not text:
            return text
        
        filtered = text
        normalized = self._normalize_text(text)
        
        for word in self.swearwords:
            if word in normalized:
                # Find and replace the word (case-insensitive)
                lower_filtered = filtered.lower()
                index = lower_filtered.find(word)
                while index != -1:
                    # Replace with asterisks matching the word length
                    filtered = filtered[:index] + (replacement * len(word)) + filtered[index + len(word):]
                    lower_filtered = filtered.lower()
                    index = lower_filtered.find(word)
        
        return filtered
    
    def get_error_message(self, matched_words):
        """Generate user-friendly error message"""
        if len(matched_words) == 1:
            return f"Your message contains inappropriate language. Please keep conversations respectful."
        else:
            return f"Your message contains inappropriate language. Please keep conversations respectful."


# Create singleton instance
swearwords_filter = SwearWordsFilter()