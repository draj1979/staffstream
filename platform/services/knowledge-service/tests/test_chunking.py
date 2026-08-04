from knowledge_service.chunking import chunk_text


def test_empty_text_yields_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_is_a_single_chunk():
    assert chunk_text("hello world", chunk_size=1000, overlap=200) == ["hello world"]


def test_long_text_is_split_with_overlap():
    text = " ".join(f"word{i}" for i in range(500))  # ~3500 chars
    chunks = chunk_text(text, chunk_size=1000, overlap=200)

    assert len(chunks) > 1
    # every chunk boundary lands on whitespace, not mid-word
    for chunk in chunks:
        assert not chunk.startswith(" ")
        assert not chunk.endswith(" ")

    # reassembling (accounting for overlap) recovers the original words
    all_words = " ".join(chunks).split()
    assert all_words[0] == "word0"
    assert "word499" in all_words


def test_chunking_terminates_on_pathological_input():
    # a single "word" longer than chunk_size has no whitespace to snap to;
    # this just proves the loop terminates rather than hanging
    text = "x" * 5000
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert sum(len(c) for c in chunks) >= len(text)
