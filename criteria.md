# Acceptance criteria for Provenance Guard

Five criteria that say what "working" means for this service, written in unit 7
**before** you built it.

**All five are yours.** None are given.

An acceptance criterion names a number or something plainly observable. *"The
detector is accurate"* is an opinion, and perfect AI detection isn't possible
anyway, so it's an opinion about something nobody can deliver. *"Of 10 pieces I
wrote myself, at most 1 is labelled high-confidence AI"* is a criterion.

Under each, write a sentence or two on **why that target**. *"I allow at most 1
false positive in 10 because on a writing site a wrong accusation costs more
than a missed detection"* is a real answer.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

---

## Pick numbers you can defend

**Cover at least three of these five areas.** They're prompts, not a form.

| Area | A question it could answer |
|---|---|
| False positives | How often may a human's writing get called AI? |
| Score spread | How far apart should clearly-AI and clearly-human text score? |
| Label coverage | Is every one of your three labels actually reachable? |
| The appeal path | Does an appeal always change status and always get recorded? |
| Bad input | What happens when `text` is missing, empty, or enormous? |

Two things worth knowing before you pick numbers:

- **The expensive mistake is one-sided.** Missing some AI text costs the site a
  little. Accusing a real writer costs that person a lot. A criterion that
  treats both errors as equally bad is describing a system nobody would ship.
- **Unit 8 tests across three trials, and the target has to hold across all
  three.** Your first signal runs a model, so identical input can score
  differently twice. A target of "at most 1 in 10" against trials of 2, 1, 2 is
  a **miss**.

---
## 1. My own writing almost never gets called AI

Of 10 pieces I wrote myself, at most 1 gets the high-confidence AI label, and
that has to hold in each of the three trials.

**Why this target:** On a writing site, telling a real person their work looks
AI-written is the worst mistake this service can make. Missing some AI text
costs the site a little. Accusing a writer costs them a lot, so I only allow
one slip in ten, and not "one on average".

---

## 2. Clearly AI and clearly human text land far apart

Across 5 pieces I'm sure are AI and 5 I'm sure are human, the average combined
score of the AI set is at least 0.30 higher than the average of the human set,
in all three trials.

**Why this target:** If the two groups score close together, the thresholds
don't mean anything and small noise flips the label. 0.30 is the width of my
unsure band (0.35 to 0.65), so a gap that size means the obvious cases should
end up on opposite sides of it instead of both sitting in the middle.

---

## 3. All three labels show up, and borderline text lands in "unsure"

Every trial produces each of the three labels at least once. Of 5 pieces I
judge borderline (AI text I edited by hand, or my own very plain writing), at
least 3 land in "unsure" in every trial.

**Why this target:** A label nobody can reach is a gap in the ranges, not a
feature. And the unsure band exists for exactly the in-between cases, so if
most of them get pushed to "human" or "AI" instead, the band isn't doing its
job.

---

## 4. Every appeal gets recorded

10 of 10 appeals with a real content_id come back with status `under_review`
and add exactly one appeal entry to `logs/audit.jsonl`. 5 of 5 appeals with a
made-up content_id come back as 404 and add nothing to the log.

**Why this target:** The appeal is the only thing a wrongly accused writer can
do. If even one appeal goes missing, that person has no way to know it was
lost, so this one has to be 100%. The 404 half matters too, because an appeal
that "succeeds" on a typo looks fine and goes nowhere.

---

## 5. Bad input never crashes the service

Missing text, empty text, text that's only spaces, a body that isn't a JSON
object, and text over 20,000 characters each get a 4xx response with an error
message. 0 of them return a 500, and each one leaves a rejection entry in the
log.

**Why this target:** These are the first things anyone poking at the service
will try, and a crash on any of them is a real outage. Logging the rejections
means I can see if someone is hammering the service with junk instead of it
just disappearing.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 8 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath, like this:

         ## 2. Uncertain cases land in the unsure band

         The system handles uncertain cases well.

         **Why this target:** ...

         > **Revised in unit 8:** Text I judged borderline scores between
         > 0.4 and 0.6 in at least 4 of 5 cases.
         >
         > **Why revised:** "well" gave me nothing to check. I couldn't
         > reach a verdict from it at all.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "At most 1 of 10 of my own pieces flagged as AI" → "at most 3
            of 10", because 1 of 10 turned out to be hard.

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
