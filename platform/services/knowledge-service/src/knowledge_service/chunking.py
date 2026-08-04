def chunk_text(text: str, *, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Fixed-size sliding-window chunking, snapped to the nearest preceding
    whitespace so chunks don't split mid-word. Simple on purpose — no
    semantic/sentence-aware splitting for this phase."""
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            snap = text.rfind(" ", start, end)
            if snap > start:
                end = snap
        else:
            end = len(text)

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)

        start = end - overlap if end - overlap > start else end

    return chunks
