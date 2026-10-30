"""Conservative offline accentuation; never predict unknown word forms."""
from functools import lru_cache
from threading import Lock

from russian_g2p.Accentor import Accentor

VOWELS = "аеёиоуыэюя"
_lock = Lock()
# Known gaps in russian_g2p's homograph data. These are review-only forms,
# not accent overrides: the teacher must supply the intended pronunciation.
_REVIEW_ONLY = frozenset({
    "мука", "муку", "мукой", "мукою", "мукам", "муками", "муках",
    "коса", "косу", "косам", "косами", "косах", "парит",
})


@lru_cache(maxsize=1)
def _accentor():
    return Accentor(mode="one", exception_for_unknown=True, use_wiki=False)


@lru_cache(maxsize=8192)
def automatic_stress(word):
    """Return a vowel offset only for a single, validated dictionary accent."""
    if word in _REVIEW_ONLY:
        return None
    # Accentor is shared across API threads. Unknown words raise instead of
    # being accumulated in its mutable bad-word list or fetched from Wiktionary.
    with _lock:
        try:
            variants = _accentor().do_accents([[word]])
        except ValueError:
            return None
    if len(variants) != 1 or len(variants[0]) != 1:
        return None
    accented = variants[0][0]
    if accented.count("+") != 1:
        return None
    plain = accented.replace("+", "")
    # The library may restore ё, but must not change spelling or offsets.
    if len(plain) != len(word) or any(
        a != b and (a, b) != ("е", "ё") for a, b in zip(word, plain)
    ):
        return None
    stress = accented.index("+") - 1  # russian_g2p marks AFTER the vowel.
    if stress < 0 or plain[stress] not in VOWELS:
        return None
    return stress
