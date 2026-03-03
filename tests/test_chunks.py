"""Unit tests for the streaming chunk helper."""


from copilot_sdk_gateway.routers.chat import split_into_chunks


class TestSplitIntoChunks:
    def test_empty_string(self):
        assert split_into_chunks("") == []

    def test_single_word(self):
        assert split_into_chunks("hello") == ["hello"]

    def test_two_words(self):
        result = split_into_chunks("hello world")
        assert result == ["hello ", "world"]

    def test_multiple_words(self):
        result = split_into_chunks("one two three four")
        assert result == ["one ", "two ", "three ", "four"]

    def test_trailing_space_on_all_but_last(self):
        result = split_into_chunks("a b c")
        assert all(r.endswith(" ") for r in result[:-1])
        assert not result[-1].endswith(" ")

    def test_whitespace_only(self):
        assert split_into_chunks("   ") == []
