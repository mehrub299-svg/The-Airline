import re

CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 150  # only used when a single paragraph is longer than CHUNK_SIZE


def _hard_split(text: str) -> list[str]:
    step = CHUNK_SIZE - CHUNK_OVERLAP
    pieces: list[str] = []
    start = 0
    while True:
        pieces.append(text[start : start + CHUNK_SIZE])
        if start + CHUNK_SIZE >= len(text):
            break
        start += step
    return pieces


def chunk_text(text: str) -> list[str]:
    """Pack whole paragraphs into chunks of at most CHUNK_SIZE characters."""
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"(?<=\S)[ \t]+", " ", text)  # collapse inner runs, keep leading indentation
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > CHUNK_SIZE:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(para))
        elif current and len(current) + 2 + len(para) > CHUNK_SIZE:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current:
        chunks.append(current)
    return chunks