import re

def format_for_whatsapp(message: str) -> str:
    """
    Format agent messages for WhatsApp.
    WhatsApp supports: *bold*, _italic_, ~strikethrough~
    """
    # Convert markdown bold (**text**) to WhatsApp bold (*text*)
    message = re.sub(r'\*\*(.*?)\*\*', r'*\1*', message)
    
    # Remove excessive line breaks
    message = re.sub(r'\n{3,}', '\n\n', message)
    
    # Limit message length (WhatsApp max is 4096 characters)
    if len(message) > 4000:
        message = message[:4000] + "...\n(Message truncated)"
    
    return message.strip()


def split_long_message(message: str, max_length: int = 4000) -> list:
    """Split long messages into multiple parts if needed"""
    if len(message) <= max_length:
        return [message]
    
    parts = []
    current_part = ""
    
    for line in message.split('\n'):
        if len(current_part) + len(line) + 1 <= max_length:
            current_part += line + '\n'
        else:
            if current_part:
                parts.append(current_part.strip())
            current_part = line + '\n'
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts