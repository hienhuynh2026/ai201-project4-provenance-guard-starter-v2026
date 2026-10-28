# Provenance Guard

> ### 👋 Start here
>
> **New to this repo? Read [RUNNING.md](RUNNING.md) first.**
>
> Once `python test.py` passes, in one terminal:
>
> ```bash
> python app.py
> ```
>
> and in another:
>
> ```bash
> curl -X POST http://127.0.0.1:5000/ping \
>   -H "Content-Type: application/json" \
>   -d '{"message": "hello"}'
> ```
>
> That's a web service. Something sent it text and it sent something back.
> Everything this unit is filling in the middle.
>
> **The rest of this file is your submission.** Fill it in as you go.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     Unit 7 asks for the first five sections. Unit 8 adds the five below.

     Everything is pasted as TEXT. A pasted curl response gets full credit;
     a picture of your terminal gets none.
     ───────────────────────────────────────────────────────────────────────── -->

<!-- ═══════════════════════ UNIT 7 — THE BUILD ═══════════════════════ -->

## What This Does

<!-- The path a submission takes, from arriving to the label a reader sees.
     Six or seven steps — this is the trace you wrote in Milestone 1. -->

1. Someone sends their text and `creator_id` as JSON to `POST /submit`
   (`app.py::submit`).
2. The route checks the input first. If the body isn't a JSON object, `text` or
   `creator_id` is missing or empty, the text is over 20,000 characters, or
   it's too short for the model to read, it sends back a 4xx error. It still
   writes a `rejected` entry to the audit log so there's a record of it.
3. Signal one (`detector.py::model_signal`) runs gpt2 on my laptop and turns
   the text's perplexity into a score from 0 to 1. Basically, how predictable
   the words are.
4. Signal two (`stylometry.py::style_signal`) looks at the shape of the text
   (how much sentence lengths vary, how varied the vocabulary is, and
   punctuation) and gives a second 0 to 1 score.
5. `scoring.py::combine_signals` turns the two scores into one. It won't let
   the score get into the AI range unless both signals agree.
6. `scoring.py::score_to_label` turns that score into a guess (`human`,
   `unsure` or `ai`) and the sentence the writer actually sees.
7. Everything gets logged to `logs/audit.jsonl` with a new `content_id`, both
   signal scores, the combined score, the label and `status: decided`. The
   same fields come back in the response.

If the writer thinks we got it wrong, they send the `content_id` and their
reason to `POST /appeal`. That adds an `appeal` entry right after the original
decision and changes the status to `under_review`. The original entry doesn't
get touched.

**The two endpoints**

| | Goes in | Comes out |
|---|---|---|
| `POST /submit` | `text` (string, 1 to 20,000 chars), `creator_id` (string) | `content_id`, `creator_id`, `guess`, `confidence` (the combined score, 0 = human, 1 = AI), `label`, `model_score`, `style_score`, `status`. Errors come back as `{error, message}` with a 400, 413 or 503 |
| `POST /appeal` | `content_id` (from `/submit`), `reasoning` (string) | `content_id`, `status: under_review`, `message`, `original_decision {guess, confidence, label}`. Errors: 400 if a field is missing, 404 if the `content_id` doesn't exist |

---

## Signals and Scoring

<!-- For each signal: what property it measures, why that might differ between
     human and AI writing, and WHAT IT CAN'T SEE.

     The blind spot is not optional. If you can't name it you don't understand
     the signal yet — and unit 8's attack set is built out of blind spots. -->

### Signal one — the model signal

**What it measures:** How predictable the text is to gpt2 (its perplexity).
Low perplexity gets a high score. A perplexity of 45 maps to 0.5, which is the
starter's default and I kept it.

**Why that might differ between human and AI writing:** AI writes by picking
likely next words, so what it writes is easy for a model to predict. People
tend to pick weirder, more specific words.

**What it can't see:** It has no idea who actually wrote the text. It mostly
rewards common words in short, normal sentences, and lots of real people write
like that: people writing in a second language, younger writers, or anyone who
just writes plainly. My plain-style test paragraph got 0.84 on this signal,
almost as high as the clearly AI one (0.92). It works the other way too. Rare
or fancy words look human to it, so swapping a few unusual words into AI text
drops the score a lot.

### Signal two — the style signal

**What it measures:** The shape of the text. It doesn't read the words at all.
I used three measures, turned each one into a 0 to 1 score with a logistic
curve (higher means more AI), and weighted them:

| Measure | What it computes | Looks like AI when | Midpoint | Weight |
|---|---|---|---|---|
| Sentence-length spread | standard deviation ÷ mean of words per sentence | low (sentences are all about the same length) | 0.40 | 0.60 |
| Punctuation density | commas, semicolons, colons, dashes, brackets, quotes, `!` and `?` per word | high | 0.06 | 0.25 |
| Type-token ratio | unique words ÷ total words, averaged over 50-word windows so length doesn't throw it off | low (same words repeat) | 0.82 | 0.15 |

If there are fewer than three sentences I set the spread part to 0.5
(neutral), since one or two sentences don't really have a spread.

**Why that might differ between human and AI writing:** AI text usually has
sentences that are all around the same medium length. People are messier, so
you get a three-word sentence right next to a really long one. In my test
samples the AI text had a spread of 0.24 and the human samples were between
0.38 and 0.74. The AI sample also used a lot more commas and similar marks
(0.08 per word, compared to 0.03 to 0.045 in the casual human posts).

**What it can't see:** What the text means. Anything that changes the shape
but not the content moves the score, like splitting up sentences, adding a
dash, or pasting in a quote. That's really easy to do on purpose. Formal human
writing with a lot of punctuation also gets pushed toward AI by the
punctuation part.

**Something I noticed:** type-token ratio barely did anything. Every sample
was between 0.77 and 0.90 whether it was AI or human, so I gave it the
smallest weight.

### The combining rule

<!-- Write the rule in words, then give the numbers. What happens when the two
     signals disagree? -->

**The rule:** I average the two signals equally. But I don't want to call
something AI unless both signals think it's AI. So if either signal is under
0.5, the combined score gets capped just below the AI threshold, which means a
split can only end up as "unsure". The cap only ever lowers a score. If both
signals say human, it still gets the human label.

**The numbers:** `WEIGHT_MODEL_SIGNAL = 0.5`, `WEIGHT_STYLE_SIGNAL = 0.5`,
`AI_AGREEMENT_FLOOR = 0.5`. The cap is `AI_THRESHOLD` minus 0.01, so 0.64. All
of these are in `config.py`.

**Where it lives:** `scoring.py::combine_signals`

<!-- ⚠️ The grader checks your code against that line. If your rule lives
     somewhere else, say where. -->

**A case where my two signals split, and what my rule does with it:**

| Input | Model | Style | Combined | Label |
|---|---|---|---|---|
| Clearly AI | 0.918 | 0.770 | 0.844 | ai |
| Clearly human (casual posts) | 0.243 | 0.170 | 0.206 | human |
| Formal human (staff prose) | 0.210 | 0.260 | 0.235 | human |
| Lightly edited AI | 0.745 | 0.492 | 0.619 | unsure |
| **Plain-style writing** | **0.844** | **0.389** | **0.617** | **unsure** |

The plain-style paragraph is where they split. The model signal thinks it's AI
because all the words are common. The style signal thinks it's human because
the sentence lengths still vary. Just averaging them gives 0.62, which is only
0.03 away from being labeled AI. With the cap it can't get into the AI range
no matter how much the model score moves between runs, because the style
signal disagrees. The downside is that the lightly edited AI sample also ends
up unsure for the same reason. The edits pushed its style score just under
0.5.

*Where the test texts came from:* the AI sample, the lightly edited AI sample
and the plain-style paragraph were written by an AI assistant to copy those
styles. The casual human text is posts by course staff from the project 3
dataset, and the formal human text is the docstring at the top of the
starter's `detector.py`. None of it is my own writing. Testing on my own
writing is what criteria.md is for.


---

## Label Variants

<!-- The exact text of all three labels, as a reader would see them, and the
     score range each covers.

     Write them for someone who has never heard the word "threshold". -->

| Label | Score range | The exact text a reader sees |
|---|---|---|
| high-confidence human | 0.00 – 0.35 | We think this was probably written by a person. |
| unsure | 0.35 – 0.65 | We can't tell whether this was written by a person or with help from AI. Lots of people's own writing lands here, so this isn't an accusation, and nothing about your post changes because of it. |
| high-confidence AI | 0.65 – 1.00 | This reads a lot like text written by AI. We can be wrong about this, especially with plain or simple writing. If you wrote it yourself, you can ask for a person to review it. |

I got all three labels with real submissions: the clearly human sample
scored 0.206 (human), the plain-style paragraph 0.617 (unsure), and the
clearly AI sample 0.844 (AI).

**Why I worded the "unsure" one this way:**
<!-- It's the hardest of the three. It has to admit uncertainty without
     sounding like an accusation, because the person reading it may well have
     written every word themselves. -->



---

## Sample Run

<!-- One submission and one appeal, pasted as text: the request, the response,
     and the log entries. -->

**A submission**

<!-- The response needs content_id, guess, confidence, label, AND both
     signal scores - model_score and style_score. Unit 8's tools read those
     two off the response, so leaving them out costs you next unit's
     diagnostics. -->

```bash
$ curl -X POST http://127.0.0.1:5001/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "I went to the store after work. They did not have the bread I like, so I got a different one. It was fine. Then I went home and made dinner for my family. My son helped me cut the vegetables. We ate at seven and watched a movie. It was a good day. I was tired so I went to bed early.", "creator_id": "sample_writer"}'
```

```json
{
    "confidence": 0.6169,
    "content_id": "af53943b-29a5-4110-9b90-0091f735baa1",
    "creator_id": "sample_writer",
    "guess": "unsure",
    "label": "We can't tell whether this was written by a person or with help from AI. Lots of people's own writing lands here, so this isn't an accusation, and nothing about your post changes because of it.",
    "model_score": 0.8444,
    "status": "decided",
    "style_score": 0.3894
}
```

**An appeal**

```bash
$ curl -X POST http://127.0.0.1:5001/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "af53943b-29a5-4110-9b90-0091f735baa1", "reasoning": "I wrote this myself. My writing is just plain."}'
```

```json
{
    "content_id": "af53943b-29a5-4110-9b90-0091f735baa1",
    "message": "Thanks. Your appeal is recorded and this decision is now under review by a person.",
    "original_decision": {
        "confidence": 0.6169,
        "guess": "unsure",
        "label": "We can't tell whether this was written by a person or with help from AI. Lots of people's own writing lands here, so this isn't an accusation, and nothing about your post changes because of it."
    },
    "status": "under_review"
}
```

**What the log shows afterwards**

```bash
$ curl "http://127.0.0.1:5001/log?limit=2"
```

```json
{
    "count": 2,
    "entries": [
        {
            "combined_score": 0.6169,
            "content_id": "af53943b-29a5-4110-9b90-0091f735baa1",
            "creator_id": "sample_writer",
            "guess": "unsure",
            "label": "We can't tell whether this was written by a person or with help from AI. Lots of people's own writing lands here, so this isn't an accusation, and nothing about your post changes because of it.",
            "model_score": 0.8444,
            "status": "decided",
            "style_score": 0.3894,
            "timestamp": "2026-10-28T22:11:28+00:00"
        },
        {
            "content_id": "af53943b-29a5-4110-9b90-0091f735baa1",
            "creator_id": "sample_writer",
            "event": "appeal",
            "reasoning": "I wrote this myself. My writing is just plain.",
            "status": "under_review",
            "timestamp": "2026-10-28T22:11:28+00:00"
        }
    ]
}
```

The original decision is still in the log with `status: decided`, and the
appeal shows up right after it with `status: under_review`. I ran the service
on port 5001 (`PORT=5001 python app.py`) because AirPlay on my Mac already
uses port 5000.

---

## How I Used AI

**Moment 1**

- *What I asked for:*
- *What came back:*
- *What I changed:*

**Moment 2**

- *What I asked for:*
- *What came back:*
- *What I changed:*

<!-- ═══════════════════════ UNIT 8 — THE TEST ═══════════════════════ -->

---

## Rate Limiting

**My limits:** ___ per minute, ___ per day

**Why those numbers and not others:**
<!-- Think about two people: a real writer submitting their own work a few
     times an hour, and a script sending a thousand variations to map your
     thresholds. Your numbers have to be liveable for the first and hostile to
     the second. -->

**What a caller counts as:** <!-- per address, or per creator_id? They fail
differently — one script can look like a thousand callers, and one household
can look like one. -->

**The run of status codes when I pushed past it:**

<!-- python run_attacks.py --flood 15 -->

```

```

---

## Attack Run — Before

<!-- Every attack with its outcome and a held-or-broke mark.
     `run_attacks.py --label before` produces the table. -->



**Ten audit log entries from the run**

<!-- Choose entries that show the interesting failures, not the ten easiest. -->

```json

```

**The single worst outcome** — the one I'd least want to explain to a writer
whose work got caught by it:



---

## Run Log and Verdicts

<!-- Your five criteria across three trials. `run_eval.py --label before`. -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |
| 2.  |  |  |  |  |  |
| 3.  |  |  |  |  |  |
| 4.  |  |  |  |  |  |
| 5.  |  |  |  |  |  |

**Real output from one trial**, pasted as text, naming the file and function
that produced it:

```json

```

**Diagnoses**

<!-- For each miss AND each broken attack: the stage and the mechanism.

     Your service has five stages: the route, signal one, signal two, the
     combining rule, and the label mapping.

     Not a diagnosis:  "The evasion attacks got through."
     A diagnosis:      "Four evasion inputs got through. All four had typos
                        added to AI-generated text. My second signal measures
                        word variety, and typos raise word variety — so it read
                        them as more human. My combining rule weights that
                        signal at 0.6, so it dragged the whole score down."

     Look for a pattern. Five failures on one signal is one problem, not five. -->



---

## The Improvement

**What I changed:**

**Which diagnosis pointed at it:**

### Attack Run — After

<!-- Same format. `run_attacks.py --label after` -->



**Did it help, and how do I know:**

<!-- Widening the unsure band usually fixes one problem and creates another.
     Reporting that trade honestly is worth full credit. -->



---

## What's Still Broken

<!-- For each attack still getting through and each criterion still missed:
     what you'd do, and why you stopped. -->



**The trade I'd make if this ran for real:**

<!-- Two sentences. Fewer wrong accusations means more AI text getting through.
     Say which way you'd go and WHO PAYS FOR IT. -->



<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 7

       [ ] criteria.md has five numbered criteria, each naming a target
       [ ] Each has a reason underneath
       [ ] POST /submit returns content_id, guess, confidence, label,
           model_score and style_score
       [ ] Two signals that measure DIFFERENT things, each with a named blind spot
       [ ] Three label variants, all reachable, written out in full
       [ ] POST /appeal changes status and writes to the log
       [ ] Signals and Scoring names scoring.py::combine_signals
       [ ] Sample Run: a submission AND an appeal, as pasted text
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN

     SUBMISSION CHECKLIST — unit 8

       [ ] Rate limiting on /submit, with your numbers justified
       [ ] The pasted run of status codes showing 429
       [ ] Audit log with all nine fields, recording rejections too
       [ ] The attack set run IN FULL, every input with an outcome
       [ ] Ten audit log entries pasted as text
       [ ] Five criteria across three trials
       [ ] A diagnosis for every miss and every broken attack — stage AND mechanism
       [ ] One improvement, with Attack Run — After
       [ ] What's Still Broken, including the production trade
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
