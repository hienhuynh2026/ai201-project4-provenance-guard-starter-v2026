"""
Signal two: the style signal. ← YOU BUILD THIS IN MILESTONE 4

Signal one reads the text for meaning. This one measures it *as text* — the
shape of it, without understanding a word.

Three measures are stubbed below because the brief names those three. They are
stubs, not implementations: what they compute is yours, and so is how you
combine them.

    sentence_length_spread   do sentences vary in length, or march in step?
    type_token_ratio         how much of the vocabulary repeats?
    punctuation_density      how much punctuation, and how varied?

Why these might differ between human and AI writing: generated prose tends
toward even, mid-length sentences and a narrower band of vocabulary, because
that's what "most likely next word" produces on average. Human writing is
lumpier — a three-word sentence next to a forty-word one.

⚠️ **The blind spot, which you have to name in Milestone 1.**

This signal cannot read. It has no idea what the text says. Anything that
changes the shape without changing the substance moves it — adding typos,
breaking up sentences, pasting in a quotation. That is a very cheap thing for
someone to do on purpose, and unit 8's attack set will do it to you.

Build each function on its own and call it from a terminal before you wire
anything together:

    python stylometry.py "some text to look at"
"""

import math
import re
import statistics

TTR_WINDOW = 50


def sentences(text: str) -> list[str]:
    """Split into sentences. Rough and good enough — given to you."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def words(text: str) -> list[str]:
    """Split into lowercase words, punctuation stripped. Given to you."""
    return re.findall(r"[a-z0-9']+", text.lower())


# ── The three measures — YOU BUILD THESE ─────────────────────────────────────

def sentence_length_spread(text: str) -> float:
    """
    How much sentence length varies. ← TODO

    Returns:
        A float. Decide yourself what scale it's on and which direction means
        "more human" — then write that down, because your combining rule
        depends on knowing it.

    A hint on what you're reaching for: the standard deviation of sentence
    lengths, probably divided by the mean so a long text and a short one are
    comparable. `statistics.stdev` is imported for you.

    Watch the edge case: a one-sentence submission has no spread at all, and
    `stdev` raises on fewer than two values. Decide what that should return
    before the attack set decides for you.
    """
    lengths = [len(words(s)) for s in sentences(text)]
    lengths = [n for n in lengths if n > 0]
    # One sentence has no spread to measure. 0.0 is the honest raw value;
    # style_signal treats it as "no evidence" rather than as "very AI".
    if len(lengths) < 2:
        return 0.0
    return statistics.stdev(lengths) / statistics.mean(lengths)


def type_token_ratio(text: str) -> float:
    """
    Unique words over total words. ← TODO

    Returns:
        A float between 0 and 1. Higher means more varied vocabulary.

    Worth knowing before you rely on it: this measure falls as text gets
    longer, because common words repeat. Two texts of different lengths aren't
    directly comparable on it, and if your test inputs vary a lot in length,
    that alone can look like a signal.
    """
    tokens = words(text)
    if not tokens:
        return 0.0
    # Moving-average TTR: the mean ratio over every 50-word window. Raw TTR
    # falls as text gets longer, so a fixed window keeps a 60-word piece and a
    # 600-word piece comparable. Shorter than one window -> plain TTR.
    if len(tokens) <= TTR_WINDOW:
        return len(set(tokens)) / len(tokens)
    ratios = [
        len(set(tokens[i:i + TTR_WINDOW])) / TTR_WINDOW
        for i in range(len(tokens) - TTR_WINDOW + 1)
    ]
    return statistics.mean(ratios)


def punctuation_density(text: str) -> float:
    """
    How much punctuation, relative to length. ← TODO

    Returns:
        A float. Whether you count all punctuation or only some kinds — commas,
        semicolons, dashes — is a real choice. Semicolons and em dashes are
        more interesting than full stops, because they vary more between
        writers.
    """
    tokens = words(text)
    if not tokens:
        return 0.0
    # Only the marks that vary between writers. Full stops just track sentence
    # count, which sentence_length_spread already sees.
    marks = re.findall(r"[,;:()\"!?\u2014\u2013]|--", text)
    return len(marks) / len(tokens)


# ── Combining them ───────────────────────────────────────────────────────────

def style_signal(text: str) -> float:
    """
    The style signal as a 0–1 score. **Higher means more likely AI.** ← TODO

    Combine your three measures into one number. Same direction as
    `detector.model_signal`, so that `scoring.combine_signals` can treat them
    the same way — if one of your signals runs backwards, everything above it
    is wrong in a way that's hard to see.

    Two things to decide and write down:

      1. Which direction each measure points. Low spread means more AI-ish, so
         it needs flipping. Work out which of your three need that.
      2. How to get each onto a comparable scale. A raw type-token ratio sits
         between 0 and 1; a raw punctuation count doesn't. Adding them
         unscaled means whichever has the bigger numbers wins by default.

    Test it on the four calibration inputs from Milestone 4 — clearly AI,
    clearly human, plain conventional human writing, lightly-edited AI — before
    you trust it. Plain and ordinary, not formal: formal prose reads as *human*
    to signal one, and it is plain writing that gets accused.
    """
    spread_ai = _flip(sentence_length_spread(text), SPREAD_MIDPOINT, SPREAD_SCALE)
    # Under three sentences the spread is mostly noise, so it says nothing.
    if len(sentences(text)) < 3:
        spread_ai = 0.5
    ttr_ai = _flip(type_token_ratio(text), TTR_MIDPOINT, TTR_SCALE)
    punct_ai = 1.0 - _flip(punctuation_density(text), PUNCT_MIDPOINT, PUNCT_SCALE)

    score = (
        WEIGHT_SPREAD * spread_ai
        + WEIGHT_TTR * ttr_ai
        + WEIGHT_PUNCT * punct_ai
    )
    return round(min(max(score, 0.0), 1.0), 4)


# Each measure goes through a logistic so it lands on 0–1 before weighting.
# Midpoints are the raw value that reads as a coin flip, set from the
# Milestone 4 calibration inputs (see README, Signals and Scoring).
#
#   spread  low  -> AI   human samples 0.38–0.74, AI sample 0.24
#   ttr     low  -> AI   barely separates anything (0.77–0.90 for all), so
#                        it gets the smallest weight
#   punct   high -> AI   the AI sample leaned on commas and dashes (0.08–0.11)
#                        where casual human posts sat at 0.03–0.045
SPREAD_MIDPOINT, SPREAD_SCALE = 0.40, 0.08
TTR_MIDPOINT, TTR_SCALE = 0.82, 0.04
PUNCT_MIDPOINT, PUNCT_SCALE = 0.06, 0.015

WEIGHT_SPREAD = 0.60
WEIGHT_PUNCT = 0.25
WEIGHT_TTR = 0.15


def _flip(value: float, midpoint: float, scale: float) -> float:
    """Logistic that is high BELOW the midpoint: 'less of this' reads as AI."""
    return 1.0 / (1.0 + math.exp((value - midpoint) / scale))


if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or (
        "The system works well. It handles most cases correctly and provides "
        "good results. Users generally find it easy to use and understand."
    )

    print(f"{len(sentences(text))} sentences, {len(words(text))} words\n")
    print(f"sentence_length_spread   {sentence_length_spread(text)}")
    print(f"type_token_ratio         {type_token_ratio(text)}")
    print(f"punctuation_density      {punctuation_density(text)}")
    print(f"style_signal             {style_signal(text)}   (higher = more likely AI)")
